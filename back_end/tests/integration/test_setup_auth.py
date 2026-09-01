# tests/integration/test_setup_auth.py
"""
Live-mongod verification of db_connector.setup_auth's decision tree.

Every test spawns real bundled mongod processes against an isolated scratch
dbpath and port (never the shared dev database on 27019), so setup_auth's
user-creation and --auth toggling never touches real data.
"""

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

import db_connector.setup_auth as setup_auth
from db_connector.settings import MongoDBSettings
from pymongo.errors import OperationFailure

pytestmark = pytest.mark.integration


# ─── Scratch environment ─────────────────────────────────────────────────

@dataclass
class Scratch:
    home: Path
    port: int

    @property
    def db_path(self) -> Path:
        return self.home / ".nlm" / "db"

    @property
    def credentials_path(self) -> Path:
        return self.home / ".nlm" / "mongodb_credentials.env"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _mongod_binary_name() -> str:
    return "mongod.exe" if sys.platform == "win32" else "mongod"


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    real_mongod = Path.home() / ".nlm" / "bin" / _mongod_binary_name()
    if not real_mongod.exists():
        pytest.skip(f"Bundled mongod not found at {real_mongod}.")

    fake_home = tmp_path / "home"
    (fake_home / ".nlm" / "bin").mkdir(parents=True)
    (fake_home / ".nlm" / "bin" / _mongod_binary_name()).symlink_to(real_mongod)

    port = _free_port()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setattr(setup_auth, "PORT", port)

    return Scratch(home=fake_home, port=port)


# ─── Bare mongod helpers — the test's own spawner, independent of setup_auth ──

def _port_open(port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def _spawn_bare_mongod(scratch: Scratch, auth: bool) -> subprocess.Popen:
    mongod_bin = scratch.home / ".nlm" / "bin" / _mongod_binary_name()
    db_path = scratch.db_path
    db_path.mkdir(parents=True, exist_ok=True)
    (db_path / "WiredTiger.lock").unlink(missing_ok=True)
    (db_path / "mongod.lock").unlink(missing_ok=True)

    args = [str(mongod_bin), "--port", str(scratch.port), "--dbpath", str(db_path), "--bind_ip", "127.0.0.1"]
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
        if _port_open(scratch.port):
            break
        time.sleep(1)
    else:
        pytest.fail("scratch mongod failed to start within 30s")
    time.sleep(1)
    return proc


def _stop_bare_mongod(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _users_via_noauth_restart(scratch: Scratch) -> list:
    """Stops whatever is running, restarts the same dbpath without --auth
    purely to enumerate every user — nlm_app itself cannot (E6), and no
    privileged credential survives setup_auth by design."""
    proc = _spawn_bare_mongod(scratch, auth=False)
    try:
        with setup_auth._client(f"mongodb://127.0.0.1:{scratch.port}/?authSource=admin") as client:
            return client.admin.command({"usersInfo": {"forAllDBs": True}})["users"]
    finally:
        _stop_bare_mongod(proc)


def _assert_role_restricted(connection_string: str, database_name: str) -> None:
    with setup_auth._client(connection_string) as client:
        client[database_name].list_collection_names()  # real read works

        for command in (
            {"createUser": "someone_else", "pwd": "x", "roles": ["readWrite"]},
            {"dropUser": setup_auth.APP_USER},
            {"usersInfo": 1},
            {"updateUser": setup_auth.APP_USER, "roles": ["root"]},
        ):
            with pytest.raises(OperationFailure) as exc:
                client.admin.command(command)
            assert exc.value.code == 13


# ─── Step 2 — Case A: new user ──────────────────────────────────────────────

def test_case_a_spawns_and_stops_its_own_mongod(scratch):
    assert not _port_open(scratch.port)

    setup_auth.run()

    assert not _port_open(scratch.port)
    assert scratch.credentials_path.stat().st_mode & 0o777 == 0o600


def test_case_a_end_state(scratch):
    proc = _spawn_bare_mongod(scratch, auth=True)
    try:
        setup_auth.run()  # attaches to the pre-spawned mongod; never stops it

        settings = MongoDBSettings.create_from_credentials()
        _assert_role_restricted(settings.mongodb_connection_string, settings.database_name)
    finally:
        _stop_bare_mongod(proc)

    settings = MongoDBSettings.create_from_credentials()
    users = _users_via_noauth_restart(scratch)
    assert len(users) == 1
    assert users[0]["user"] == setup_auth.APP_USER
    assert users[0]["db"] == "admin"
    assert users[0]["roles"] == [{"role": "readWrite", "db": settings.database_name}]


# ─── Step 3 — Case D: idempotency ───────────────────────────────────────────

def test_case_d_idempotent(scratch):
    proc = _spawn_bare_mongod(scratch, auth=True)
    try:
        setup_auth.run()
        before = scratch.credentials_path.read_bytes()

        setup_auth.run()
        after = scratch.credentials_path.read_bytes()

        assert before == after
    finally:
        _stop_bare_mongod(proc)


# ─── Step 4 — Case C: existing install with real data ───────────────────────

def test_case_c_preserves_data_and_avoids_double_spawn(scratch, monkeypatch):
    proc = _spawn_bare_mongod(scratch, auth=False)
    try:
        with setup_auth._client(f"mongodb://127.0.0.1:{scratch.port}/?authSource=admin") as client:
            client["custom_db"]["some_collection"].insert_many([{"n": 1}, {"n": 2}, {"n": 3}])

        scratch.home.joinpath(".nlm", "mongodb_credentials.env").write_text(
            f'MONGODB_CONNECTION_STRING="mongodb://127.0.0.1:{scratch.port}/"\n'
            'DATABASE_NAME="custom_db"\n',
            encoding="utf-8",
        )

        lock_path = scratch.db_path / "WiredTiger.lock"
        mtime_before = lock_path.stat().st_mtime if lock_path.exists() else None

        def _fail_if_spawned():
            pytest.fail("setup_auth spawned a second mongod despite one already running")

        monkeypatch.setattr(setup_auth, "_spawn_mongod", _fail_if_spawned)

        setup_auth.run()

        if mtime_before is not None:
            assert lock_path.stat().st_mtime == mtime_before

        settings = MongoDBSettings.create_from_credentials()
        assert settings.database_name == "custom_db"

        with setup_auth._client(settings.mongodb_connection_string) as client:
            count = client["custom_db"]["some_collection"].count_documents({})
        assert count == 3
    finally:
        _stop_bare_mongod(proc)


# ─── Upgrade: passwordless credential against an --auth mongod ───────────────

def test_upgrade_passwordless_credential_creates_and_demotes(scratch):
    # The real upgrade state: a passwordless credentials file already exists,
    # and mongod is enforcing --auth with zero users. An anonymous read returns
    # 13, which must NOT be mistaken for an un-demoted interrupted run.
    proc = _spawn_bare_mongod(scratch, auth=True)
    try:
        scratch.credentials_path.write_text(
            f'MONGODB_CONNECTION_STRING="mongodb://127.0.0.1:{scratch.port}/"\n'
            'DATABASE_NAME="legacy_db"\n',
            encoding="utf-8",
        )

        setup_auth.run()

        settings = MongoDBSettings.create_from_credentials()
        assert settings.database_name == "legacy_db"  # preserved
        from pymongo.uri_parser import parse_uri
        assert parse_uri(settings.mongodb_connection_string)["username"] == setup_auth.APP_USER
        _assert_role_restricted(settings.mongodb_connection_string, settings.database_name)
    finally:
        _stop_bare_mongod(proc)

    users = _users_via_noauth_restart(scratch)
    assert len(users) == 1
    assert users[0]["user"] == setup_auth.APP_USER
    assert users[0]["roles"] == [{"role": "readWrite", "db": "legacy_db"}]


# ─── Step 6b — Interrupted create-then-demote ───────────────────────────────

def test_resumes_when_killed_between_createUser_and_demote(scratch):
    proc = _spawn_bare_mongod(scratch, auth=True)
    try:
        password = setup_auth._generate_password()
        uri = setup_auth._build_uri(password)
        with setup_auth._client(setup_auth._anonymous_uri()) as client:
            client.admin.command("createUser", setup_auth.APP_USER, pwd=password, roles=["userAdminAnyDatabase"])
        setup_auth._write_credentials_file(uri, "nlm_translator")
        # Deliberately no _demote() call — simulates the interrupted window.

        setup_auth.run()  # must resume, not report a lockout

        settings = MongoDBSettings.create_from_credentials()
        with setup_auth._client(settings.mongodb_connection_string) as client:
            assert client[settings.database_name].list_collection_names() == []
    finally:
        _stop_bare_mongod(proc)


def test_refuses_when_killed_between_createUser_and_file_write(scratch, capsys):
    proc = _spawn_bare_mongod(scratch, auth=True)
    try:
        password = setup_auth._generate_password()
        with setup_auth._client(setup_auth._anonymous_uri()) as client:
            client.admin.command("createUser", setup_auth.APP_USER, pwd=password, roles=["userAdminAnyDatabase"])
        # No credentials file written — simulates a crash before the write.

        exit_code = setup_auth.main()
        captured = capsys.readouterr()

        assert exit_code != 0
        assert not scratch.credentials_path.exists()
        assert "Drop the existing users" in captured.err
    finally:
        _stop_bare_mongod(proc)


# ─── Step 8 — Refusal state ──────────────────────────────────────────────────

def test_refusal_state_attempts_no_repair(scratch, capsys):
    proc = _spawn_bare_mongod(scratch, auth=True)
    try:
        setup_auth.run()
        settings = MongoDBSettings.create_from_credentials()
        scratch.credentials_path.unlink()

        exit_code = setup_auth.main()
        captured = capsys.readouterr()

        assert exit_code != 0
        assert "Drop the existing users" in captured.err

        # No repair attempted: auth is still enforced.
        with pytest.raises(OperationFailure) as exc:
            with setup_auth._client(setup_auth._anonymous_uri()) as client:
                client[settings.database_name].list_collection_names()
        assert exc.value.code in (13, 18)
    finally:
        _stop_bare_mongod(proc)
