"""
Live-mongod confirmation of the enforcement probe (Verification Step 5).

Spawns real bundled mongod on an isolated free port — never the shared dev
database on 27019 — and confirms the probe passes against an --auth server and
fatally rejects a no-auth one.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from db_connector.auth_probe import AuthEnforcementError, verify_auth_enforced
from db_connector.settings import MongoDBSettings

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _mongod_binary() -> Path:
    name = "mongod.exe" if sys.platform == "win32" else "mongod"
    return Path.home() / ".nlm" / "bin" / name


def _port_open(port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def _spawn(port: int, db_path: Path, auth: bool) -> subprocess.Popen:
    db_path.mkdir(parents=True, exist_ok=True)
    (db_path / "WiredTiger.lock").unlink(missing_ok=True)
    (db_path / "mongod.lock").unlink(missing_ok=True)

    args = [str(_mongod_binary()), "--port", str(port), "--dbpath", str(db_path), "--bind_ip", "127.0.0.1"]
    if auth:
        args.append("--auth")

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "GLIBC_TUNABLES": "glibc.pthread.rseq=0"} if sys.platform == "linux" else {**os.environ},
    )
    for _ in range(30):
        if proc.poll() is not None:
            pytest.fail("scratch mongod exited during startup")
        if _port_open(port):
            break
        time.sleep(1)
    else:
        pytest.fail("scratch mongod failed to start within 30s")
    time.sleep(1)
    return proc


def _stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture
def scratch(tmp_path):
    if not _mongod_binary().exists():
        pytest.skip(f"Bundled mongod not found at {_mongod_binary()}.")
    return _free_port(), tmp_path / "db"


def _settings_for(port: int) -> MongoDBSettings:
    return MongoDBSettings(
        mongodb_connection_string=f"mongodb://127.0.0.1:{port}/",
        database_name="nlm_translator",
    )


def test_probe_passes_against_auth_mongod(scratch):
    port, db_path = scratch
    proc = _spawn(port, db_path, auth=True)
    try:
        # Zero users + --auth: an anonymous read is refused (13), which is a pass.
        verify_auth_enforced(_settings_for(port))
    finally:
        _stop(proc)


def test_probe_is_fatal_against_noauth_mongod(scratch):
    port, db_path = scratch
    proc = _spawn(port, db_path, auth=False)
    try:
        with pytest.raises(AuthEnforcementError):
            verify_auth_enforced(_settings_for(port))
    finally:
        _stop(proc)
