# tests/conftest.py
"""Pytest configuration for USFM parser tests."""

import sys
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

# Add the back_end directory to Python path for imports
# This allows imports like `from utils.usfm_parser import ...`
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


@pytest.fixture(scope="session", autouse=True)
def _ensure_mongod():
    """Start bundled mongod on port 27019 if not already running."""

    def _port_open():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", 27019))
            s.close()
            return True
        except OSError:
            return False

    if _port_open():
        # Already running (Electron or manual) — do not touch it.
        yield
        return

    mongod_name = "mongod.exe" if sys.platform == "win32" else "mongod"
    mongod_bin = Path.home() / ".nlm" / "bin" / mongod_name
    if not mongod_bin.exists():
        pytest.fail(f"Bundled mongod not found at {mongod_bin}. Run the download script first.")

    db_path = Path.home() / ".nlm" / "db"
    db_path.mkdir(parents=True, exist_ok=True)
    (db_path / "WiredTiger.lock").unlink(missing_ok=True)
    (db_path / "mongod.lock").unlink(missing_ok=True)

    proc = subprocess.Popen(
        [str(mongod_bin), "--port", "27019", "--dbpath", str(db_path), "--bind_ip", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "GLIBC_TUNABLES": "glibc.pthread.rseq=0"} if sys.platform == "linux" else {**os.environ},
    )

    # Poll until port opens or process dies
    for _ in range(30):
        if proc.poll() is not None:
            break
        if _port_open():
            break
        time.sleep(1)
    else:
        pytest.fail("mongod failed to start within 30s.")

    if not _port_open():
        pytest.fail(f"mongod exited early (code {proc.returncode}).")

    # TCP port is open but WiredTiger may still be initializing.
    # Give mongod a moment to finish internal startup before tests connect.
    time.sleep(1)

    yield

    # Teardown: we spawned it, so we stop it.
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
