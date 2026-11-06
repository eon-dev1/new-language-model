# db_connector/sqlite_connection.py
"""
SQLite connection helper.

Not wired into the app yet: no route, tool, or util imports this module.

A ``sqlite3.Connection`` is pinned to the OS thread that created it, and
``asyncio.to_thread`` dispatches onto a shared, multi-worker pool — so a
connection opened in one ``to_thread`` call cannot be safely queried or closed
in a later one (the second call routinely lands on a different worker thread).
This module therefore never hands a connection across a thread boundary. The
whole open → PRAGMA → BEGIN → work → COMMIT → close lifecycle runs inside a
single ``to_thread`` call via :func:`run_db`, which takes the caller's work as
a callback.
"""

import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")

BUSY_TIMEOUT_MS = 5000


def _default_db_path() -> Path:
    return Path.home() / ".nlm" / "data" / "nlm.sqlite3"


def _run(db_path: Path, fn: Callable[[sqlite3.Connection], T], write: bool = False) -> T:
    """
    Synchronously open ``db_path``, apply the PRAGMAs, run ``fn(conn)`` inside
    one transaction, commit it, and close the connection — all on one thread.

    The caller contract (what ``write`` does, what ``fn`` may and may not do,
    and every failure path) is documented on :func:`run_db`.
    """
    db_dir = db_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        db_dir.chmod(0o700)

    # isolation_level=None: sqlite3 issues no implicit BEGIN/COMMIT; _run owns
    # both. (The legacy default opens a transaction before DML but not before
    # SELECT, which would leave check-then-write logic non-atomic.)
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        # All three reissued every call: foreign_keys is connection-scoped and
        # resets on every new connection; journal_mode=WAL is file-scoped so
        # reissuing it past the first connection is a harmless no-op;
        # busy_timeout absorbs ordinary SQLITE_BUSY contention from concurrent
        # connections. All must precede BEGIN: foreign_keys is a no-op inside a
        # transaction and journal_mode can't change inside one.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

        if os.name == "posix":
            db_path.chmod(0o600)

        if write:
            # Take the write lock before fn's first read, so read-then-write in
            # fn can't race another writer or hit SQLITE_BUSY_SNAPSHOT.
            conn.execute("BEGIN IMMEDIATE")
        else:
            # A write in read mode fails loudly instead of slipping through.
            # Deferred BEGIN gives fn one consistent WAL snapshot without ever
            # waiting on a writer.
            conn.execute("PRAGMA query_only = ON")
            conn.execute("BEGIN")
        result = fn(conn)
        conn.execute("COMMIT")
        return result
    finally:
        try:
            # Discard anything uncommitted. close() alone is deferred while fn
            # left a partly-read cursor alive (e.g. referenced by a raised
            # exception's traceback), which would keep the write lock held for
            # as long as that traceback lives. No-op after COMMIT.
            conn.rollback()
        finally:
            if os.name == "posix":
                # WAL's -wal/-shm sidecars are created lazily on first write (not
                # at PRAGMA time) and inherit the process umask, so this is the
                # point in the lifecycle where they may exist and need locking
                # down. They are removed again when the last connection closes,
                # so this chmod only persists while another connection keeps the
                # file open — the concurrent case it exists to cover.
                # Confidentiality is held by the 0o700 directory regardless.
                # Chmod before close(), which may delete them.
                for suffix in ("-wal", "-shm"):
                    sidecar = db_path.with_name(db_path.name + suffix)
                    if sidecar.exists():
                        sidecar.chmod(0o600)
            conn.close()


async def run_db(
    fn: Callable[[sqlite3.Connection], T],
    db_path: Path | None = None,
    *,
    write: bool = False,
) -> T:
    """
    Run ``fn`` in one transaction on a freshly-opened SQLite connection to
    ``~/.nlm/data/nlm.sqlite3`` (or ``db_path`` if given), returning ``fn``'s
    result.

    A new connection is opened per call — no shared/cached connection: WAL's
    concurrent-reader benefit comes from separate connections each holding their
    own snapshot, and a shared connection would risk one caller's transaction
    bleeding into another's across an ``await``.

    ``run_db`` begins the transaction before calling ``fn`` and commits it after
    ``fn`` returns; ``fn`` never commits. If ``fn`` raises, everything it wrote
    is discarded.

    - ``write=False`` (default): read-only. The connection is set to
      ``query_only``, so any write raises ``OperationalError("attempt to write a
      readonly database")``. A deferred ``BEGIN`` gives every statement in
      ``fn`` the same consistent snapshot, and never waits on a writer.
    - ``write=True``: ``BEGIN IMMEDIATE`` takes the database write lock before
      ``fn`` runs (waiting up to ``BUSY_TIMEOUT_MS`` for another writer), so
      reads inside ``fn`` see the latest committed state and nothing else can
      write between ``fn``'s reads and its writes.

    Rules for ``fn``:

    - One call is one transaction. Anything that must be atomic has to happen
      inside one ``write=True`` call — including read-then-write logic (a
      duplicate check followed by an insert) and pairs of related writes (e.g.
      a tool's write together with clearing ``pending_tool_call``).
    - Keep write calls short. Do expensive computation (tokenizing, counting,
      parsing) before the ``write=True`` call, so the lock is held only for the
      writes; other writers give up after ``BUSY_TIMEOUT_MS``.
    - The only allowed exception to "one call is one transaction" is derived
      data that the next change rebuilds anyway: the word and phrase index
      builders may read source rows in one call, compute, and write in a
      separate ``write=True`` call. A verse saved in between is missing from
      that rebuild, but every verse save triggers its own word-index rebuild
      (serialized behind ``_rebuild_lock``) and a debounced phrase-index rebuild after it commits, and that later
      rebuild includes it.
    - Do not end or begin transactions: no ``commit()``, ``rollback()``,
      ``executescript()`` (which commits first), or ``BEGIN``.
    - Catch only ``sqlite3.IntegrityError`` inside ``fn``: a constraint
      violation leaves the transaction open. Let every other ``sqlite3`` error
      propagate — after errors such as a full disk or I/O failure SQLite may
      already have rolled the transaction back, and any later statement would
      then autocommit on its own.
    - Return materialized values (``fetchall()`` results, scalars), never
      ``conn`` or a cursor; the connection is closed as soon as ``fn`` returns.

    What the caller sees:

    - ``fn`` raises (e.g. ``IntegrityError`` on a UNIQUE violation): nothing is
      committed, the lock is released, and ``fn``'s original exception
      propagates.
    - Another writer still holds the lock after ``BUSY_TIMEOUT_MS``:
      ``BEGIN IMMEDIATE`` raises ``OperationalError("database is locked")``
      before ``fn`` runs. There is no automatic retry — in a single-user app,
      that much contention means something is wrong.
    - ``fn`` writes in read mode: the first write statement raises
      ``OperationalError("attempt to write a readonly database")``.
    - ``fn`` ends the transaction itself (``commit()``/``rollback()``/
      ``executescript()``), or catches a non-integrity ``sqlite3`` error after
      SQLite ended it, and keeps going: statements after that point autocommit
      and stay durable, then ``run_db``'s COMMIT raises
      ``OperationalError("cannot commit - no transaction is active")``. The
      mistake surfaces, but is not prevented.
    - COMMIT itself fails (disk full, I/O error): the transaction is rolled
      back and the ``OperationalError`` propagates.
    - ``fn`` issues ``BEGIN``: ``OperationalError("cannot start a transaction
      within a transaction")`` at that statement.
    - The awaiting coroutine is cancelled: the worker thread keeps running and
      still commits; the caller gets ``CancelledError`` and the result is
      dropped.

    ``db_path`` lets a caller target a non-default file (e.g. a scratch/stress
    database) without monkeypatching ``Path.home()``.
    """
    return await asyncio.to_thread(_run, db_path or _default_db_path(), fn, write)
