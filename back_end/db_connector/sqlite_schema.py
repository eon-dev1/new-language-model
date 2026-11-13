# db_connector/sqlite_schema.py
"""
SQLite DDL for the application's data store.

``init_schema`` creates every table and index if they do not already exist.
It is idempotent and safe to call on every boot. It does not migrate a file
that already has these tables — a later schema change is a rebuild or an
ALTER, not a re-run of this function.

Table shapes:
- JSON-blob tables (``languages``, ``bible_books``, ``grammar_systems``,
  ``correction_log``) keep the document in ``data`` and promote only
  filter/sort keys as generated STORED columns.
- Flat tables (``bible_texts``, ``base_structure_bible``, ``notes``,
  ``word_index``, ``phrase_index``) are ordinary typed columns.
- Parent+child (``dictionaries``/``entries``, ``chat_conversations``/``messages``)
  split arrays that are mutated as individual rows.

``id TEXT PRIMARY KEY`` does not imply ``NOT NULL`` in SQLite (unlike
``INTEGER PRIMARY KEY``), so every ``id`` column declares it explicitly.
"""

import sqlite3

DDL_STATEMENTS: list[str] = [
    """CREATE TABLE IF NOT EXISTS languages (
        id TEXT PRIMARY KEY NOT NULL,
        data TEXT NOT NULL,
        language_code TEXT NOT NULL UNIQUE
            GENERATED ALWAYS AS (json_extract(data, '$.language_code')) STORED
    )""",

    # english_text_lc / translated_text_lc are application-maintained lowercase
    # copies of verse text. They cannot be GENERATED columns: SQLite's lower()
    # is ASCII-only, which would miss diacritic-bearing target languages.
    # Writers must populate both columns.
    """CREATE TABLE IF NOT EXISTS bible_texts (
        id TEXT PRIMARY KEY NOT NULL,
        language_code TEXT NOT NULL,
        book_code TEXT NOT NULL CHECK (book_code <> '' AND book_code NOT GLOB '*[^a-z0-9_]*'),
        chapter INTEGER NOT NULL,
        verse INTEGER NOT NULL,
        english_text TEXT,
        translated_text TEXT,
        human_verified INTEGER NOT NULL DEFAULT 0,
        language_name TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        footnotes TEXT,
        english_text_lc TEXT,
        translated_text_lc TEXT,
        UNIQUE (language_code, book_code, chapter, verse)
    )""",
    # No language_code index: the UNIQUE constraint's index already leads with it.
    "CREATE INDEX IF NOT EXISTS idx_bible_texts_book_code ON bible_texts(book_code)",

    """CREATE TABLE IF NOT EXISTS bible_books (
        id TEXT PRIMARY KEY NOT NULL,
        data TEXT NOT NULL,
        language_code TEXT NOT NULL
            GENERATED ALWAYS AS (json_extract(data, '$.language_code')) STORED,
        book_code TEXT NOT NULL
            GENERATED ALWAYS AS (json_extract(data, '$.book_code')) STORED,
        canonical_order INTEGER
            GENERATED ALWAYS AS (json_extract(data, '$.metadata.canonical_order')) STORED,
        UNIQUE (language_code, book_code)
    )""",
    # No separate language_code index: the UNIQUE constraint's index already leads with it.

    """CREATE TABLE IF NOT EXISTS base_structure_bible (
        id TEXT PRIMARY KEY NOT NULL,
        book TEXT NOT NULL,
        chapter INTEGER NOT NULL,
        verse INTEGER NOT NULL,
        book_order INTEGER NOT NULL CHECK (book_order BETWEEN 1 AND 66),
        testament TEXT NOT NULL,
        language_code TEXT NOT NULL DEFAULT 'base',
        is_base_structure INTEGER NOT NULL DEFAULT 1,
        text TEXT,
        translation TEXT,
        created_at TEXT,
        updated_at TEXT,
        UNIQUE (book, chapter, verse)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_base_structure_bible_book_order ON base_structure_bible(book_order)",

    # Real columns, not a JSON blob: entry_count is incremented in SQL
    # (`entry_count = entry_count + 1`), which only works on a real column.
    # categories and metadata are the only JSON TEXT columns on this table.
    """CREATE TABLE IF NOT EXISTS dictionaries (
        id TEXT PRIMARY KEY NOT NULL,
        language_code TEXT NOT NULL UNIQUE,
        dictionary_name TEXT NOT NULL,
        entry_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        language_name TEXT,
        categories TEXT,
        metadata TEXT
    )""",
    # Deleting a dictionary (or conversation, below) must remove its child
    # rows; without CASCADE, foreign_keys=ON turns that delete into a
    # constraint error.
    # examples is always a JSON array. Legacy rows stored this as a list, a
    # bare string, or omitted it; writers and migration normalize those to
    # [] so a DEFAULT of '[]' matches the empty case.
    # word must already be in normalize_word() form (shared/storage_conventions.py)
    # when written, and non-empty: the primary key compares bytes, so "Tok" and
    # "tok" would otherwise be two rows. SQL cannot check this, because SQLite's
    # lower() is ASCII-only and it has no Unicode normalization.
    """CREATE TABLE IF NOT EXISTS entries (
        dictionary_id TEXT NOT NULL REFERENCES dictionaries(id) ON DELETE CASCADE,
        word TEXT NOT NULL,
        definition TEXT NOT NULL,
        part_of_speech TEXT,
        human_verified INTEGER NOT NULL DEFAULT 0,
        etymology TEXT,
        examples TEXT NOT NULL DEFAULT '[]',
        created_at TEXT,
        updated_at TEXT,
        PRIMARY KEY (dictionary_id, word)
    )""",

    """CREATE TABLE IF NOT EXISTS grammar_systems (
        id TEXT PRIMARY KEY NOT NULL,
        data TEXT NOT NULL,
        language_code TEXT NOT NULL UNIQUE
            GENERATED ALWAYS AS (json_extract(data, '$.language_code')) STORED
    )""",

    """CREATE TABLE IF NOT EXISTS correction_log (
        id TEXT PRIMARY KEY NOT NULL,
        data TEXT NOT NULL,
        language_code TEXT NOT NULL
            GENERATED ALWAYS AS (json_extract(data, '$.language_code')) STORED,
        content_type TEXT NOT NULL
            GENERATED ALWAYS AS (json_extract(data, '$.content_type')) STORED,
        created_at TEXT NOT NULL
            GENERATED ALWAYS AS (json_extract(data, '$.created_at')) STORED
    )""",
    "CREATE INDEX IF NOT EXISTS idx_correction_log_language_time ON correction_log(language_code, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_correction_log_language_type_time ON correction_log(language_code, content_type, created_at DESC)",

    """CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY NOT NULL,
        language_code TEXT NOT NULL,
        title TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_notes_language_code ON notes(language_code)",

    """CREATE TABLE IF NOT EXISTS chat_conversations (
        id TEXT PRIMARY KEY NOT NULL,
        title TEXT NOT NULL,
        message_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        pending_tool_call TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated_at ON chat_conversations(updated_at DESC)",
    """CREATE TABLE IF NOT EXISTS messages (
        conversation_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
        seq INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        tool_calls TEXT,
        thinking_content TEXT,
        PRIMARY KEY (conversation_id, seq)
    )""",

    # Rebuilt from bible_texts, never looked up by a surrogate id. The natural
    # unique pair is the primary key.
    """CREATE TABLE IF NOT EXISTS word_index (
        language_code TEXT NOT NULL,
        word TEXT NOT NULL,
        total_count INTEGER NOT NULL,
        book_count INTEGER NOT NULL,
        chapter_count INTEGER NOT NULL,
        occurrences TEXT NOT NULL,
        first_seen TEXT NOT NULL,
        in_dictionary INTEGER NOT NULL DEFAULT 0,
        last_rebuilt TEXT NOT NULL,
        PRIMARY KEY (language_code, word)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_word_index_frequency_sort ON word_index(language_code, total_count DESC)",
    "CREATE INDEX IF NOT EXISTS idx_word_index_dictionary_gap ON word_index(language_code, in_dictionary)",

    # Same rationale as word_index: rebuilt, not migrated; keyed by the
    # natural unique pair.
    """CREATE TABLE IF NOT EXISTS phrase_index (
        language_code TEXT NOT NULL,
        phrase TEXT NOT NULL,
        n INTEGER NOT NULL,
        df INTEGER NOT NULL,
        min_word_df INTEGER NOT NULL,
        locations TEXT NOT NULL,
        last_rebuilt TEXT NOT NULL,
        PRIMARY KEY (language_code, phrase)
    )""",
]


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Create every table/index if absent. Idempotent — safe to call on every boot.

    Must run inside a write transaction: ``await run_db(init_schema, write=True)``.
    """
    for statement in DDL_STATEMENTS:
        conn.execute(statement)
