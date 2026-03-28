"""
Unit tests for the Bible verse search endpoint.

TDD: run these first (all fail / collection-error), then implement
the search_bible_verses handler in routes/bible_reader.py (all pass).

Test grouping:
  Tests 1-3, 5-7 — call handler directly with mock_db (no HTTP layer)
  Test 4          — uses TestClient (FastAPI validates min_length=2
                    before the handler runs, so no DB mock needed)

asyncio_mode = auto is set in pytest.ini — no @pytest.mark.asyncio needed.
"""

import re
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from routes.bible_reader import search_bible_verses
from constants import Collection


# ─── Async cursor helper ──────────────────────────────────────────────────────

async def async_iter(docs):
    """
    Mimics a Motor async cursor.

    Motor cursors support `async for` via __aiter__/__anext__. A plain
    AsyncMock does NOT implement these, so `async for doc in cursor` raises
    TypeError. This generator is the correct substitute.
    """
    for doc in docs:
        yield doc


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_collection():
    """Mock Motor collection for bible_texts."""
    return MagicMock()


@pytest.fixture
def mock_db(mock_collection):
    """
    Mock MongoDBConnector.

    db.get_database()[Collection.BIBLE_TEXTS] → mock_collection.

    Collection.BIBLE_TEXTS is a str Enum ("bible_texts"), so dict lookup
    works with either the enum value or the raw string — they compare equal.
    """
    db = MagicMock()
    db.get_database.return_value = {Collection.BIBLE_TEXTS: mock_collection}
    return db


def make_find_side_effect(english_docs, target_docs):
    """
    Returns a callable side_effect for mock_collection.find().

    FOOTGUN PREVENTION: find() is called twice — once for the English cursor,
    once for the target cursor. If we set return_value to a single generator,
    the second call gets the already-exhausted iterator and yields nothing
    silently. Using side_effect as a callable returns a fresh generator on
    every call. Keyed on language_code to distinguish the two queries.
    """
    def _side_effect(query, **kwargs):
        if query.get("language_code") == "english":
            return async_iter(list(english_docs))
        return async_iter(list(target_docs))
    return _side_effect


# ─── TestClient (Test 4 only) ─────────────────────────────────────────────────

# No DB override needed: FastAPI's Query(min_length=2) validation fires before
# the handler is called, so the DB is never touched for a rejected query.
client = TestClient(app)


# ─── Tests 1-3, 5-7: handler-direct ──────────────────────────────────────────

async def test_verse_matching_both_languages_deduplicated(mock_db, mock_collection):
    """
    A verse whose text matches in both English and the target language
    must appear exactly once in results — not twice.

    Forces the merge-dict pattern. Without it, naive list concatenation
    (english_results + target_results) would return the same verse twice.
    """
    english_doc = {
        "book_code": "genesis", "chapter": 1, "verse": 1,
        "english_text": "In the beginning God created light."
    }
    target_doc = {
        "book_code": "genesis", "chapter": 1, "verse": 1,
        "translated_text": "Kope translation mentioning light."
    }
    mock_collection.find.side_effect = make_find_side_effect([english_doc], [target_doc])

    result = await search_bible_verses("kope", q="light", limit=50, db=mock_db)

    assert result.count == 1
    assert len(result.results) == 1
    assert result.results[0].book_code == "genesis"


async def test_missing_translated_text_returns_none_not_keyerror(mock_db, mock_collection):
    """
    A target-language doc with no 'translated_text' key must not crash.

    Forces doc.get("translated_text") instead of doc["translated_text"].
    Documents with missing fields exist in real data (incomplete imports).
    """
    target_doc = {"book_code": "genesis", "chapter": 1, "verse": 1}
    mock_collection.find.side_effect = make_find_side_effect([], [target_doc])

    result = await search_bible_verses("kope", q="beginning", limit=50, db=mock_db)

    assert result.count == 1
    assert result.results[0].translated_text is None


async def test_limit_applied_to_combined_not_per_query(mock_db, mock_collection):
    """
    The limit must be applied to the merged output, not per-cursor.

    30 unique English + 30 unique target = 60 combined; limit=50 must cap at 50.
    If limit is applied per-cursor, each returns up to 50, merged total = 100.
    """
    english_docs = [
        {"book_code": "genesis", "chapter": 1, "verse": i, "english_text": f"the verse {i}"}
        for i in range(1, 31)
    ]
    target_docs = [
        {"book_code": "genesis", "chapter": 2, "verse": i, "translated_text": f"the target {i}"}
        for i in range(1, 31)
    ]
    mock_collection.find.side_effect = make_find_side_effect(english_docs, target_docs)

    result = await search_bible_verses("kope", q="the", limit=50, db=mock_db)

    assert len(result.results) == 50
    assert result.count == 50


async def test_no_matches_returns_empty_list_not_404(mock_db, mock_collection):
    """
    Zero search results must return 200 with an empty list, not raise 404.

    get_chapter_verses raises 404 for empty chapters. Copy-pasting that
    pattern to search would make "no results" an error state, breaking
    the frontend's empty-state display.
    """
    mock_collection.find.side_effect = make_find_side_effect([], [])

    result = await search_bible_verses("kope", q="xyzimpossible", limit=50, db=mock_db)

    assert result.count == 0
    assert result.results == []
    assert result.query == "xyzimpossible"


async def test_re_escape_applied_to_query(mock_db, mock_collection):
    """
    re.escape(q) must be applied before building the MongoDB regex filter.

    With a mock DB the invalid regex "[a" is never evaluated by MongoDB,
    so a TestClient "returns 200" assertion would pass even without re.escape.
    Instead, inspect the query dict passed to find() and assert it contains
    the escaped string — the only meaningful unit-test proof that re.escape
    is in the implementation.
    """
    mock_collection.find.side_effect = make_find_side_effect([], [])

    await search_bible_verses("kope", q="[a", limit=50, db=mock_db)

    first_call_query = mock_collection.find.call_args_list[0][0][0]
    assert first_call_query["english_text"]["$regex"] == re.escape("[a")
    # re.escape("[a") == "\\[a" — a valid literal regex, not the raw "[a"


async def test_english_only_match_has_no_translated_text(mock_db, mock_collection):
    """
    A verse matched only in English (target not yet translated) must appear
    in results with translated_text=None.

    This is the most common real-world case for languages with partial
    translation coverage.
    """
    english_doc = {
        "book_code": "genesis", "chapter": 1, "verse": 1,
        "english_text": "In the beginning God created the heavens."
    }
    mock_collection.find.side_effect = make_find_side_effect([english_doc], [])

    result = await search_bible_verses("kope", q="beginning", limit=50, db=mock_db)

    assert result.count == 1
    assert result.results[0].english_text != ""
    assert result.results[0].translated_text is None


# ─── Test 4: TestClient (validation before handler) ───────────────────────────

def test_single_character_query_rejected():
    """
    A query shorter than min_length=2 must return 422 before hitting the DB.

    Tests that Query(..., min_length=2) is declared on the endpoint.
    Without it, single-character queries fire full-corpus regex scans.
    """
    response = client.get("/api/verses/kope/search?q=a")
    assert response.status_code == 422
