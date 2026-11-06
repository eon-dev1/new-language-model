# tests/unit/db_connector/test_sqlite_schema.py
"""
SQLite schema unit tests.

Proves idempotent init via
run_db, the 13 tables, TEXT PK NOT NULL, natural-key PKs on the rebuilt
indexes, CHECK rejection of the adversarial book_code/book_order inputs,
generated-column extraction, UNIQUE conflict targets, ON DELETE CASCADE
(with foreign_keys actually on), and entries.examples defaulting to '[]'.

These tests run under pytest-asyncio's default (multi-worker) executor with
no pinning, matching test_sqlite_connection.py.
"""

import json
import sqlite3

import pytest

from db_connector.sqlite_connection import run_db
from db_connector.sqlite_schema import init_schema


EXPECTED_TABLES = frozenset({
    "languages",
    "bible_texts",
    "bible_books",
    "base_structure_bible",
    "dictionaries",
    "entries",
    "grammar_systems",
    "correction_log",
    "notes",
    "chat_conversations",
    "messages",
    "word_index",
    "phrase_index",
})

MIGRATED_TOP_LEVEL = (
    "languages",
    "bible_texts",
    "bible_books",
    "base_structure_bible",
    "dictionaries",
    "grammar_systems",
    "correction_log",
    "notes",
    "chat_conversations",
)


@pytest.fixture(autouse=True)
def _fake_home(tmp_path, monkeypatch):
    """Redirect Path.home() so schema init never touches the real ~/.nlm/data/."""
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
    return tmp_path


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]


def _table_info(conn: sqlite3.Connection, table: str) -> list[tuple]:
    return conn.execute(f"PRAGMA table_info({table})").fetchall()


def _create_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    assert row is not None, f"table {table!r} missing"
    return row[0]


class TestIdempotencyAndRunDb:
    async def test_init_schema_via_run_db(self, tmp_path):
        """The actual integration point: await run_db(init_schema, db_path=..., write=True)."""
        target = tmp_path / "schema.sqlite3"
        await run_db(init_schema, db_path=target, write=True)
        tables = await run_db(_table_names, db_path=target)
        assert set(tables) == EXPECTED_TABLES

    async def test_init_schema_twice_does_not_raise(self):
        def _twice(conn):
            init_schema(conn)
            init_schema(conn)
            return _table_names(conn)

        tables = await run_db(_twice, write=True)
        assert set(tables) == EXPECTED_TABLES


class TestTablePresence:
    async def test_all_13_tables_present(self):
        await run_db(init_schema, write=True)
        tables = await run_db(_table_names)
        assert set(tables) == EXPECTED_TABLES
        assert len(tables) == 13


class TestPrimaryKeys:
    @pytest.mark.parametrize("table", MIGRATED_TOP_LEVEL)
    async def test_id_is_not_null_on_migrated_top_level(self, table):
        await run_db(init_schema, write=True)
        cols = await run_db(lambda c: _table_info(c, table))
        id_col = next((c for c in cols if c[1] == "id"), None)
        assert id_col is not None, f"{table} has no id column"
        # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
        assert id_col[3] == 1, f"{table}.id is not NOT NULL"

    @pytest.mark.parametrize(
        "table, pk_sql",
        [
            ("word_index", "PRIMARY KEY (language_code, word)"),
            ("phrase_index", "PRIMARY KEY (language_code, phrase)"),
        ],
    )
    async def test_rebuilt_indexes_use_natural_key_pk(self, table, pk_sql):
        await run_db(init_schema, write=True)

        def _inspect(conn):
            names = [c[1] for c in _table_info(conn, table)]
            return names, _create_sql(conn, table)

        names, sql = await run_db(_inspect)
        assert "id" not in names
        assert pk_sql in sql


class TestCheckConstraints:
    def _insert_bible_text(self, conn, row_id, book_code):
        conn.execute(
            """INSERT INTO bible_texts
               (id, language_code, book_code, chapter, verse, created_at)
               VALUES (?, 'en', ?, 1, 1, 't')""",
            (row_id, book_code),
        )

    def _insert_base_structure(self, conn, row_id, book_order):
        conn.execute(
            """INSERT INTO base_structure_bible
               (id, book, chapter, verse, book_order, testament)
               VALUES (?, 'Genesis', 1, 1, ?, 'OT')""",
            (row_id, book_order),
        )

    @pytest.mark.parametrize("book_code", ["aB!#", "g; DROP TABLE x", ""])
    async def test_book_code_check_rejects(self, book_code):
        await run_db(init_schema, write=True)
        with pytest.raises(sqlite3.IntegrityError):
            await run_db(lambda c: self._insert_bible_text(c, "v1", book_code), write=True)

    @pytest.mark.parametrize("book_code", ["genesis", "1_corinthians"])
    async def test_book_code_check_accepts(self, book_code):
        await run_db(init_schema, write=True)
        await run_db(lambda c: self._insert_bible_text(c, "v1", book_code), write=True)
        stored = await run_db(
            lambda c: c.execute("SELECT book_code FROM bible_texts").fetchone()[0]
        )
        assert stored == book_code

    @pytest.mark.parametrize("book_order", [0, 67])
    async def test_book_order_check_rejects(self, book_order):
        await run_db(init_schema, write=True)
        with pytest.raises(sqlite3.IntegrityError):
            await run_db(lambda c: self._insert_base_structure(c, "b1", book_order), write=True)

    @pytest.mark.parametrize("book_order", [1, 66])
    async def test_book_order_check_accepts(self, book_order):
        await run_db(init_schema, write=True)
        await run_db(lambda c: self._insert_base_structure(c, "b1", book_order), write=True)
        stored = await run_db(
            lambda c: c.execute(
                "SELECT book_order FROM base_structure_bible"
            ).fetchone()[0]
        )
        assert stored == book_order


class TestGeneratedColumns:
    async def test_generated_columns_extract_from_json(self):
        await run_db(init_schema, write=True)

        def _insert(conn):
            conn.execute(
                "INSERT INTO languages (id, data) VALUES (?, ?)",
                ("lang1", json.dumps({"language_code": "english"})),
            )
            conn.execute(
                "INSERT INTO bible_books (id, data) VALUES (?, ?)",
                (
                    "bb1",
                    json.dumps({
                        "language_code": "tok_pisin",
                        "book_code": "genesis",
                        "metadata": {"canonical_order": 1},
                    }),
                ),
            )
            conn.execute(
                "INSERT INTO correction_log (id, data) VALUES (?, ?)",
                (
                    "cl1",
                    json.dumps({
                        "language_code": "bughotu",
                        "content_type": "verse",
                        "created_at": "2024-01-01T00:00:00.000000+00:00",
                    }),
                ),
            )

        await run_db(_insert, write=True)

        def _read(conn):
            lang = conn.execute(
                "SELECT language_code FROM languages WHERE id='lang1'"
            ).fetchone()
            book = conn.execute(
                "SELECT language_code, book_code, canonical_order "
                "FROM bible_books WHERE id='bb1'"
            ).fetchone()
            log = conn.execute(
                "SELECT language_code, content_type, created_at "
                "FROM correction_log WHERE id='cl1'"
            ).fetchone()
            return lang, book, log

        lang, book, log = await run_db(_read)
        assert lang == ("english",)
        assert book == ("tok_pisin", "genesis", 1)
        assert log == (
            "bughotu",
            "verse",
            "2024-01-01T00:00:00.000000+00:00",
        )


class TestUniqueConstraints:
    async def test_languages_language_code_unique(self):
        """Generated-column UNIQUE — Phase 2 ON CONFLICT(language_code) target."""
        await run_db(init_schema, write=True)
        payload = json.dumps({"language_code": "english"})

        def _first(conn):
            conn.execute(
                "INSERT INTO languages (id, data) VALUES (?, ?)",
                ("a", payload),
            )

        await run_db(_first, write=True)

        def _dup(conn):
            conn.execute(
                "INSERT INTO languages (id, data) VALUES (?, ?)",
                ("b", payload),
            )

        with pytest.raises(sqlite3.IntegrityError):
            await run_db(_dup, write=True)

    async def test_bible_texts_verse_lookup_unique(self):
        await run_db(init_schema, write=True)

        def _insert(conn, row_id):
            conn.execute(
                """INSERT INTO bible_texts
                   (id, language_code, book_code, chapter, verse, created_at)
                   VALUES (?, 'en', 'genesis', 1, 1, 't')""",
                (row_id,),
            )

        await run_db(lambda c: _insert(c, "v1"), write=True)
        with pytest.raises(sqlite3.IntegrityError):
            await run_db(lambda c: _insert(c, "v2"), write=True)

    async def test_entries_dictionary_id_word_unique(self):
        await run_db(init_schema, write=True)

        def _parent_and_first(conn):
            conn.execute(
                """INSERT INTO dictionaries
                   (id, language_code, dictionary_name, created_at)
                   VALUES ('d1', 'en', 'English', 't')"""
            )
            conn.execute(
                """INSERT INTO entries (dictionary_id, word, definition)
                   VALUES ('d1', 'hello', 'greeting')"""
            )

        await run_db(_parent_and_first, write=True)

        def _dup(conn):
            conn.execute(
                """INSERT INTO entries (dictionary_id, word, definition)
                   VALUES ('d1', 'hello', 'other')"""
            )

        with pytest.raises(sqlite3.IntegrityError):
            await run_db(_dup, write=True)

    async def test_word_index_language_code_word_unique(self):
        await run_db(init_schema, write=True)

        def _insert(conn):
            conn.execute(
                """INSERT INTO word_index
                   (language_code, word, total_count, book_count, chapter_count,
                    occurrences, first_seen, last_rebuilt)
                   VALUES ('en', 'hello', 1, 1, 1, '[]', '{}', 't')"""
            )

        await run_db(_insert, write=True)
        with pytest.raises(sqlite3.IntegrityError):
            await run_db(_insert, write=True)


class TestForeignKeyCascade:
    """CASCADE must be observed with PRAGMA foreign_keys = ON.

    Drive these through run_db: a raw sqlite3.connect() leaves FKs off and
    would false-pass a missing CASCADE.
    """

    async def test_deleting_dictionary_cascades_to_entries(self):
        await run_db(init_schema, write=True)

        def _setup_and_delete(conn):
            conn.execute(
                """INSERT INTO dictionaries
                   (id, language_code, dictionary_name, created_at)
                   VALUES ('d1', 'en', 'English', 't')"""
            )
            conn.execute(
                """INSERT INTO entries (dictionary_id, word, definition)
                   VALUES ('d1', 'hello', 'greeting')"""
            )
            before = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            conn.execute("DELETE FROM dictionaries WHERE id='d1'")
            after = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            return before, after

        before, after = await run_db(_setup_and_delete, write=True)
        assert before == 1
        assert after == 0

    async def test_deleting_conversation_cascades_to_messages(self):
        await run_db(init_schema, write=True)

        def _setup_and_delete(conn):
            conn.execute(
                """INSERT INTO chat_conversations
                   (id, title, created_at, updated_at)
                   VALUES ('c1', 'hi', 't', 't')"""
            )
            conn.execute(
                """INSERT INTO messages
                   (conversation_id, seq, role, content, timestamp)
                   VALUES ('c1', 0, 'user', 'hello', 't')"""
            )
            before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            conn.execute("DELETE FROM chat_conversations WHERE id='c1'")
            after = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            return before, after

        before, after = await run_db(_setup_and_delete, write=True)
        assert before == 1
        assert after == 0


class TestEntriesExamplesDefault:
    async def test_examples_defaults_to_empty_json_array(self):
        await run_db(init_schema, write=True)

        def _insert_without_examples(conn):
            conn.execute(
                """INSERT INTO dictionaries
                   (id, language_code, dictionary_name, created_at)
                   VALUES ('d1', 'en', 'English', 't')"""
            )
            conn.execute(
                """INSERT INTO entries (dictionary_id, word, definition)
                   VALUES ('d1', 'hello', 'greeting')"""
            )
            return conn.execute(
                "SELECT examples FROM entries WHERE word='hello'"
            ).fetchone()[0]

        assert await run_db(_insert_without_examples, write=True) == "[]"
