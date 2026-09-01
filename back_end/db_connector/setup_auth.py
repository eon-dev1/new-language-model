# db_connector/setup_auth.py
#
# python -m db_connector.setup_auth
#
# Creates the MongoDB application user against the bundled mongod and writes
# ~/.nlm/mongodb_credentials.env. Safe to re-run: it recognizes its own
# already-valid credential ("Already configured") and resumes its own
# interrupted runs. It never repairs a lockout — it prints the manual
# recovery procedure and exits non-zero instead.

import base64
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)
from pymongo.uri_parser import parse_uri

from db_connector.settings import MongoDBSettings
from shared.logging_setup import redact

HOST = "127.0.0.1"
PORT = 27019
APP_USER = "nlm_app"
SERVER_SELECTION_TIMEOUT_MS = 5000

_RECOVERY_MESSAGE = (
    "MongoDB already has users configured, but no working credential was found\n"
    "(mongodb_credentials.env is missing, or its credential no longer authenticates).\n"
    "Your data is intact — this only affects access. This script does not repair\n"
    "that automatically. To recover:\n"
    "  1. Stop the app.\n"
    "  2. Start mongod WITHOUT --auth on the same dbpath.\n"
    "  3. Drop the existing users from the admin database.\n"
    "  4. Stop mongod, then re-run: python -m db_connector.setup_auth\n"
)


class SetupAuthError(Exception):
    """A fatal, non-retryable setup_auth failure; str(self) is the user-facing message."""


# ─── Paths — resolved fresh on every call, never cached at import time, so
# tests can redirect them by monkeypatching Path.home(). ────────────────────

def _credentials_path() -> Path:
    return Path.home() / ".nlm" / "mongodb_credentials.env"


def _db_path() -> Path:
    return Path.home() / ".nlm" / "db"


def _mongod_bin() -> Path:
    name = "mongod.exe" if sys.platform == "win32" else "mongod"
    return Path.home() / ".nlm" / "bin" / name


# ─── mongod lifecycle — same spawn and lock-file policy as
# tests/conftest.py::_ensure_mongod, plus --auth. ───────────────────────────

def _port_open() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((HOST, PORT))
        s.close()
        return True
    except OSError:
        return False


def _spawn_mongod() -> subprocess.Popen:
    mongod_bin = _mongod_bin()
    if not mongod_bin.exists():
        raise SetupAuthError(
            f"Bundled mongod not found at {mongod_bin}. Run 'npm run prepare:mongo' in front_end/ first."
        )

    db_path = _db_path()
    db_path.mkdir(parents=True, exist_ok=True)
    # Port confirmed closed by the caller, so any lock here is stale.
    (db_path / "WiredTiger.lock").unlink(missing_ok=True)
    (db_path / "mongod.lock").unlink(missing_ok=True)

    print("Started a temporary MongoDB instance — do not launch the app until this finishes.")

    proc = subprocess.Popen(
        [str(mongod_bin), "--port", str(PORT), "--dbpath", str(db_path), "--bind_ip", HOST, "--auth"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "GLIBC_TUNABLES": "glibc.pthread.rseq=0"} if sys.platform == "linux" else {**os.environ},
    )

    for _ in range(30):
        if proc.poll() is not None:
            break
        if _port_open():
            break
        time.sleep(1)
    else:
        raise SetupAuthError("mongod failed to start within 30s.")

    if not _port_open():
        raise SetupAuthError(f"mongod exited early (code {proc.returncode}).")

    # TCP port is open but WiredTiger may still be initializing.
    time.sleep(1)
    return proc


def _stop_mongod(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ─── Credential helpers ─────────────────────────────────────────────────────

def _generate_password() -> str:
    # base64url, not standard base64: a MongoDB URI requires percent-encoding
    # of : / ? # [ ] @ % in userinfo, and standard base64's alphabet ('/','+')
    # would intermittently corrupt the URI depending on the random bytes.
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def _build_uri(password: str) -> str:
    # authSource=admin: createUser on a non-admin database is rejected even
    # via the localhost exception, so the account always lives in admin.
    return f"mongodb://{APP_USER}:{password}@{HOST}:{PORT}/?authSource=admin"


def _anonymous_uri() -> str:
    return f"mongodb://{HOST}:{PORT}/?authSource=admin"


def _client(uri: str) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS, directConnection=True)


def _load_existing_settings():
    if not _credentials_path().is_file():
        return None
    try:
        return MongoDBSettings.create_from_credentials()
    except (FileNotFoundError, ValueError):
        return None


def _uri_has_userinfo(uri: str) -> bool:
    # A passwordless URI (the pre-auth upgrade state) has no username, so it
    # connects anonymously. Under --auth an anonymous read returns 13 — the
    # same code an authenticated-but-under-privileged user returns — so the
    # decision tree must not treat it as an authenticating credential.
    try:
        return bool(parse_uri(uri).get("username"))
    except Exception:
        return False


def _resolve_new_database_name() -> str:
    # No credentials file exists yet — resolve DATABASE_NAME the same way
    # MongoDBSettings normally would (env var, else its class default) by
    # constructing one with a throwaway connection string.
    return MongoDBSettings(mongodb_connection_string="mongodb://placeholder/").database_name


def _write_credentials_file(connection_string: str, database_name: str) -> None:
    nlm_dir = Path.home() / ".nlm"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    nlm_dir.chmod(0o700)

    content = (
        "# NLM — MongoDB credentials\n"
        "# Generated by: python -m db_connector.setup_auth\n"
        "# Read by:      back_end/db_connector/settings.py (create_from_credentials)\n"
        "#\n"
        "# This file contains a live password. Do NOT commit or share it.\n"
        "# Lost it? See README.md § Recovering a lost credential.\n"
        "\n"
        f'MONGODB_CONNECTION_STRING="{connection_string}"\n'
        f'DATABASE_NAME="{database_name}"\n'
    )

    fd, tmp_name = tempfile.mkstemp(dir=str(nlm_dir), prefix=".mongodb_credentials.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(_credentials_path()))
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


# ─── The decision tree ──────────────────────────────────────────────────────

def _demote(connection_string: str, database_name: str) -> None:
    # A userAdminAnyDatabase holder can update its own roles down to
    # readWrite, but afterwards cannot re-grant itself anything broader —
    # this is what makes create-then-demote safe to leave interrupted.
    with _client(connection_string) as client:
        client.admin.command("updateUser", APP_USER, roles=[{"role": "readWrite", "db": database_name}])


def _verify(connection_string: str, database_name: str) -> None:
    with _client(connection_string) as client:
        client[database_name].list_collection_names()


def _confirm_anonymous_refused(database_name: str) -> None:
    # Soft confirmation only — _verify() above is the real gate. Never let
    # this secondary check fail the whole run.
    try:
        with _client(_anonymous_uri()) as client:
            client[database_name].list_collection_names()
        print("Warning: an anonymous connection could still read the database after setup.")
    except OperationFailure as e:
        if e.code in (13, 18):
            print("Confirmed: anonymous access is refused.")
        else:
            print(f"Could not confirm anonymous refusal: {redact(str(e))}")
    except PyMongoError as e:
        print(f"Could not confirm anonymous refusal: {redact(str(e))}")


def _create_then_demote(database_name: str) -> str:
    """Runs the localhost-exception create, writes the file, then demotes. Returns the new URI."""
    password = _generate_password()
    uri = _build_uri(password)

    try:
        with _client(_anonymous_uri()) as client:
            client.admin.command("createUser", APP_USER, pwd=password, roles=["userAdminAnyDatabase"])
    except OperationFailure as e:
        if e.code == 13:
            raise SetupAuthError(_RECOVERY_MESSAGE) from e
        raise

    # Written before demotion: the localhost exception closes the instant
    # this user exists, so a crash between here and the updateUser call
    # below must be resumable — see _handle_auth_on's e.code == 13 branch.
    _write_credentials_file(uri, database_name)

    _demote(uri, database_name)
    return uri


def _handle_auth_on(existing_settings, database_name: str) -> None:
    # Only a credential that actually carries userinfo can be "Already
    # configured" or a resumable interrupted run. A missing file or a
    # passwordless upgrade file falls through to create-then-demote — the
    # plan's "the stored credential does not authenticate" branch.
    if existing_settings is not None and _uri_has_userinfo(existing_settings.mongodb_connection_string):
        try:
            with _client(existing_settings.mongodb_connection_string) as client:
                client[database_name].list_collection_names()
            print("Already configured.")
            return
        except OperationFailure as e:
            if e.code == 13:
                # Authenticates but can't read: an un-demoted user left by an
                # interrupted run. Resume in place rather than recreating.
                _demote(existing_settings.mongodb_connection_string, database_name)
                _verify(existing_settings.mongodb_connection_string, database_name)
                _confirm_anonymous_refused(database_name)
                print(f"Resumed an interrupted run — {APP_USER} is now demoted and verified.")
                return
            if e.code != 18:
                raise
            # 18 == AuthenticationFailed: the stored credential is stale/wrong. Fall through.
        except (ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError) as e:
            raise SetupAuthError(
                f"Could not reach MongoDB with the stored credential: {redact(str(e))}"
            ) from e

    uri = _create_then_demote(database_name)
    _verify(uri, database_name)
    _confirm_anonymous_refused(database_name)
    print(f"Created {APP_USER} and wrote {_credentials_path()}.")


def _handle_auth_off(database_name: str) -> None:
    # E1 does not apply when auth is off: create with the final role directly.
    password = _generate_password()
    uri = _build_uri(password)

    with _client(_anonymous_uri()) as client:
        client.admin.command(
            "createUser", APP_USER, pwd=password,
            roles=[{"role": "readWrite", "db": database_name}],
        )
    _write_credentials_file(uri, database_name)
    _verify(uri, database_name)
    print(f"Created {APP_USER} directly — MongoDB is not currently enforcing authentication.")
    print("Enforcement begins the next time mongod is started with --auth.")


def run() -> None:
    spawned = None
    try:
        if not _port_open():
            spawned = _spawn_mongod()
        else:
            print(f"Using the MongoDB instance already listening on {HOST}:{PORT}.")

        existing_settings = _load_existing_settings()
        database_name = existing_settings.database_name if existing_settings else _resolve_new_database_name()

        try:
            with _client(_anonymous_uri()) as client:
                client[database_name].list_collection_names()
            auth_is_on = False
        except OperationFailure as e:
            if e.code not in (13, 18):
                raise
            auth_is_on = True
        except (ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError) as e:
            raise SetupAuthError(f"Could not reach MongoDB at {HOST}:{PORT}: {redact(str(e))}") from e

        if auth_is_on:
            _handle_auth_on(existing_settings, database_name)
        else:
            _handle_auth_off(database_name)
    finally:
        if spawned is not None:
            _stop_mongod(spawned)


def main() -> int:
    try:
        run()
    except SetupAuthError as e:
        print(str(e), file=sys.stderr)
        return 1
    except PyMongoError as e:
        print(f"MongoDB setup failed: {redact(str(e))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
