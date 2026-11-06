# tests/unit/db_connector/test_sqlite_connection.py
"""
SQLite Connection Unit Tests

Tests the SQLite connection helper against a temp-directory home, never the
real ~/.nlm/data/.

These tests run under pytest-asyncio's default (multi-worker) executor with no
pinning. That is deliberate: the helper's whole contract is that no connection
object ever crosses a thread boundary, and only the real multi-worker executor
exercises that. The concurrency test below is the regression guard for the
original cross-thread bug.
"""

import asyncio
import os
import sqlite3
import stat
from unittest import mock

import pytest

from db_connector.sqlite_connection import (
    run_db,
    _run,
    _default_db_path,
    BUSY_TIMEOUT_MS,
)


@pytest.fixture(autouse=True)
def _fake_home(tmp_path, monkeypatch):
    """Redirect Path.home() so the helper never touches the real ~/.nlm/data/."""
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
    return tmp_path


def _write_locked(db_path) -> bool:
    """True if another connection holds the write lock (fails fast, no waiting)."""
    probe = sqlite3.connect(db_path, isolation_level=None, timeout=0)
    try:
        probe.execute("BEGIN IMMEDIATE")
        return False
    except sqlite3.OperationalError as e:
        if "locked" not in str(e):
            raise
        return True
    finally:
        probe.close()


class TestDefaultPath:
    def test_default_db_path(self, _fake_home):
        assert _default_db_path() == _fake_home / ".nlm" / "data" / "nlm.sqlite3"


class TestPragmas:
    """PRAGMAs are applied on every connection run_db opens."""

    async def test_journal_mode_is_wal(self):
        mode = await run_db(lambda c: c.execute("PRAGMA journal_mode").fetchone()[0])
        assert mode == "wal"

    async def test_foreign_keys_enabled(self):
        enabled = await run_db(lambda c: c.execute("PRAGMA foreign_keys").fetchone()[0])
        assert enabled == 1

    async def test_busy_timeout_configured(self):
        timeout = await run_db(lambda c: c.execute("PRAGMA busy_timeout").fetchone()[0])
        assert timeout == BUSY_TIMEOUT_MS


class TestConnectionLifecycle:
    """Fresh connection per call; separate connections see each other's commits."""

    async def test_separate_connections_see_committed_writes(self):
        def _write(c):
            c.execute("CREATE TABLE t (x INTEGER)")
            c.execute("INSERT INTO t VALUES (7)")

        await run_db(_write, write=True)
        # A second, independent run_db call (its own connection) reads the row
        # the first committed — proving genuinely separate connections to the
        # same file, not one shared/cached object.
        value = await run_db(lambda c: c.execute("SELECT x FROM t").fetchone()[0])
        assert value == 7

    async def test_creates_db_at_expected_path(self, _fake_home):
        await run_db(lambda c: None)
        assert (_fake_home / ".nlm" / "data" / "nlm.sqlite3").is_file()

    async def test_explicit_db_path_overrides_default(self, _fake_home, tmp_path):
        """An explicit db_path is used verbatim, not _default_db_path()."""
        target = tmp_path / "custom" / "elsewhere.sqlite3"

        def _write(c):
            c.execute("CREATE TABLE t (x INTEGER)")
            c.execute("INSERT INTO t VALUES (99)")

        value = await run_db(
            lambda c: (_write(c), c.execute("SELECT x FROM t").fetchone()[0])[1],
            db_path=target,
            write=True,
        )
        assert value == 99
        # The write landed at the given path, and the default location was never
        # created (the parent dir under the fake home stays absent).
        assert target.is_file()
        assert not (_fake_home / ".nlm" / "data" / "nlm.sqlite3").exists()


class TestConcurrency:
    """Regression guard for the original cross-thread bug.

    Under the multi-worker default executor, many concurrent run_db calls must
    each complete their whole open->write->commit->close lifecycle on a single
    thread without a connection leaking across threads, and SQLite's WAL locking
    plus busy_timeout must serialize the concurrent writes rather than crash.
    """

    async def test_concurrent_writers_no_crash_no_lost_writes(self):
        n = 30

        # Pre-create the table once so workers only contend on INSERT, not DDL.
        await run_db(lambda c: c.execute("CREATE TABLE t (i INTEGER)").close(), write=True)

        def _insert(i):
            def _fn(c):
                c.execute("INSERT INTO t VALUES (?)", (i,))
            return _fn

        results = await asyncio.gather(
            *[run_db(_insert(i), write=True) for i in range(n)],
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, Exception)]
        assert errors == [], f"concurrent run_db raised: {errors[:3]}"

        count = await run_db(lambda c: c.execute("SELECT COUNT(*) FROM t").fetchone()[0])
        assert count == n


class TestTransactions:
    """run_db owns BEGIN/COMMIT; fn never commits."""

    @staticmethod
    async def _create_table(db):
        await run_db(
            lambda c: c.execute("CREATE TABLE t (x INTEGER)").close(),
            db_path=db,
            write=True,
        )

    async def test_read_mode_rejects_writes(self, tmp_path):
        db = tmp_path / "t.sqlite3"
        await self._create_table(db)
        # Match the message, not sqlite_errorname (absent before Python 3.11).
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            await run_db(lambda c: c.execute("INSERT INTO t VALUES (1)").close(), db_path=db)

    async def test_write_rolled_back_when_fn_raises(self, tmp_path):
        db = tmp_path / "t.sqlite3"
        await self._create_table(db)

        def _insert_then_raise(c):
            c.execute("INSERT INTO t VALUES (1)")
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await run_db(_insert_then_raise, db_path=db, write=True)
        count = await run_db(lambda c: c.execute("SELECT COUNT(*) FROM t").fetchone()[0], db_path=db)
        assert count == 0

    async def test_write_lock_held_during_fn(self, tmp_path):
        """The write lock is taken before fn's first statement, which is what
        makes read-then-write inside one write=True call atomic."""
        db = tmp_path / "t.sqlite3"
        await self._create_table(db)
        assert await run_db(lambda c: _write_locked(db), db_path=db, write=True)

    async def test_write_lock_released_while_exception_alive(self, tmp_path):
        """
        fn raises while its partly-read cursor is still referenced by the
        exception's traceback. That pending statement defers close(), so with
        close() alone the write lock (and the uncommitted INSERT) would stay
        held for as long as the traceback lives. The explicit rollback must
        release it immediately.
        """
        db = tmp_path / "t.sqlite3"
        await self._create_table(db)
        await run_db(
            lambda c: c.execute("INSERT INTO t VALUES (1), (2)").close(),
            db_path=db,
            write=True,
        )

        def _partial_read_then_raise(c):
            cur = c.execute("SELECT x FROM t")
            cur.fetchone()  # one of two rows: the statement stays pending
            c.execute("INSERT INTO t VALUES (9)")
            raise ValueError("boom")

        with pytest.raises(ValueError) as excinfo:
            await run_db(_partial_read_then_raise, db_path=db, write=True)
        # excinfo is still in scope here, so the traceback (and cur) are alive.
        assert not _write_locked(db)

    async def test_fn_commit_then_write_raises(self, tmp_path):
        """
        An fn that commits mid-way surfaces as an error from run_db's COMMIT.
        Rows 1 and 2 are both durable regardless (row 2 autocommits): this
        proves the mistake surfaces, not that it is prevented. Pins
        isolation_level=None — in sqlite3's legacy mode the second INSERT would
        silently open a new transaction and run_db's COMMIT would succeed.
        """
        db = tmp_path / "t.sqlite3"
        await self._create_table(db)

        def _commit_midway(c):
            c.execute("INSERT INTO t VALUES (1)")
            c.commit()
            c.execute("INSERT INTO t VALUES (2)")

        with pytest.raises(sqlite3.OperationalError, match="no transaction"):
            await run_db(_commit_midway, db_path=db, write=True)


class TestExceptionSafety:
    """_run must close the connection whether fn succeeds or raises."""

    def test_connection_closed_when_fn_raises(self, _fake_home):
        captured = {}
        real_connect = sqlite3.connect

        def _spy(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            captured["conn"] = conn
            return conn

        def _boom(_conn):
            raise ValueError("boom")

        db_path = _fake_home / ".nlm" / "data" / "nlm.sqlite3"
        with mock.patch("sqlite3.connect", side_effect=_spy):
            with pytest.raises(ValueError, match="boom"):
                _run(db_path, _boom)

        # The captured connection must be closed — any use raises ProgrammingError.
        with pytest.raises(sqlite3.ProgrammingError):
            captured["conn"].execute("SELECT 1")


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
class TestPosixPermissions:
    """Credential-file-style permissions: 0o700 dir, 0o600 db file (and sidecars)."""

    async def test_directory_permissions(self, _fake_home):
        await run_db(lambda c: None)
        db_dir = _fake_home / ".nlm" / "data"
        assert stat.S_IMODE(db_dir.stat().st_mode) == 0o700

    async def test_db_file_permissions(self, _fake_home):
        await run_db(lambda c: None)
        db_file = _fake_home / ".nlm" / "data" / "nlm.sqlite3"
        assert stat.S_IMODE(db_file.stat().st_mode) == 0o600

    async def test_wal_sidecars_chmodded(self, _fake_home):
        db_file = _fake_home / ".nlm" / "data" / "nlm.sqlite3"
        wal = db_file.with_name(db_file.name + "-wal")
        shm = db_file.with_name(db_file.name + "-shm")

        # Establish the DB + WAL mode.
        await run_db(lambda c: c.execute("CREATE TABLE t (x)").close(), write=True)

        # -wal/-shm are deleted when the LAST connection closes, so hold a
        # keep-alive connection open on this thread. That keeps them alive past
        # the next run_db's close, letting us observe the chmod result — which is
        # also the only real-world state the sidecar chmod matters in (concurrent
        # overlapping connections).
        keep = sqlite3.connect(db_file)
        try:
            keep.execute("SELECT COUNT(*) FROM t").fetchone()  # establishes -shm
            await run_db(lambda c: c.execute("INSERT INTO t VALUES (1)").close(), write=True)
            assert wal.exists() and shm.exists()
            assert stat.S_IMODE(wal.stat().st_mode) == 0o600
            assert stat.S_IMODE(shm.stat().st_mode) == 0o600
        finally:
            keep.close()
