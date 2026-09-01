"""
Verification Step 9 — the backup path against an authenticated instance must
not leak the password into the HTTP response or the logs.

Now that the URI carries a live password (previously passwordless), this
confirms mongodump receives it via the temp config file only, and that
nothing echoes it back to the caller or the log stream.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from db_connector.settings import MongoDBSettings
from pymongo import MongoClient

pytestmark = pytest.mark.integration

_PASSWORD = "STEP9secretPW_do_not_leak_ABC123"  # URI-safe, distinctive for grepping
_APP_USER = "nlm_app"
_DB = "nlm_translator"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _bin(name: str) -> Path:
    ext = ".exe" if sys.platform == "win32" else ""
    return Path.home() / ".nlm" / "bin" / f"{name}{ext}"


def _port_open(port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def _spawn_auth_mongod(port: int, db_path: Path) -> subprocess.Popen:
    db_path.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [str(_bin("mongod")), "--port", str(port), "--dbpath", str(db_path), "--bind_ip", "127.0.0.1", "--auth"],
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


@pytest.mark.asyncio
async def test_backup_against_auth_instance_does_not_leak_password(tmp_path, caplog):
    if not _bin("mongod").exists() or not _bin("mongodump").exists():
        pytest.skip("Bundled mongod/mongodump not found.")

    port = _free_port()
    proc = _spawn_auth_mongod(port, tmp_path / "db")
    try:
        anon = f"mongodb://127.0.0.1:{port}/?authSource=admin"
        with MongoClient(anon, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            # Localhost exception: create privileged, then demote to readWrite.
            client.admin.command("createUser", _APP_USER, pwd=_PASSWORD, roles=["userAdminAnyDatabase"])

        authed = f"mongodb://{_APP_USER}:{_PASSWORD}@127.0.0.1:{port}/?authSource=admin"
        with MongoClient(authed, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            client.admin.command("updateUser", _APP_USER, roles=[{"role": "readWrite", "db": _DB}])
            client[_DB]["sample"].insert_many([{"n": 1}, {"n": 2}])

        settings = MongoDBSettings(mongodb_connection_string=authed, database_name=_DB)

        from routes.db_backup import BackupRequest, backup_database

        out_dir = tmp_path / "backups"
        out_dir.mkdir()
        with caplog.at_level("INFO"):
            response = await backup_database(BackupRequest(output_dir=str(out_dir)), settings=settings)

        assert response.success
        assert _PASSWORD not in response.backup_dir
        assert _PASSWORD not in response.message
        log_text = "\n".join(rec.getMessage() for rec in caplog.records)
        assert _PASSWORD not in log_text
    finally:
        _stop(proc)
