"""
Tests for sync_bible_books_from_texts's canonical output shape.

Asserts emitted bible_books docs have `chapters == [{chapter, verse_count}, ...]`
sorted by chapter, with no `chapter_number` key and no embedded `verses` array.

MockDB gap: the shared phrase_index/conftest.py MockDB has no `aggregate` or
`update_one` support, so this module builds a minimal per-test mock instead of
lifting the shared MockDB up.
"""

import pytest
from unittest.mock import MagicMock

from utils.usfm_parser.usfm_importer import sync_bible_books_from_texts


class _FakeCursor:
    """Minimal async cursor stand-in for collection.aggregate(pipeline)."""

    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for item in self._items:
            yield item


class _FakeTextsCollection:
    def __init__(self, agg_result):
        self._agg_result = agg_result
        self.last_pipeline = None

    def aggregate(self, pipeline):
        self.last_pipeline = pipeline
        return _FakeCursor(self._agg_result)


class _FakeBooksCollection:
    def __init__(self):
        self.update_calls = []

    async def update_one(self, filter_doc, update_doc, upsert=False):
        self.update_calls.append((filter_doc, update_doc, upsert))
        return MagicMock()


class _FakeDB:
    def __init__(self, texts_coll, books_coll):
        self._collections = {"bible_texts": texts_coll, "bible_books": books_coll}

    def __getitem__(self, name):
        return self._collections[name]


class _FakeConnector:
    def __init__(self, db):
        self._db = db

    def get_database(self):
        return self._db


def _make_connector(agg_result):
    texts = _FakeTextsCollection(agg_result)
    books = _FakeBooksCollection()
    db = _FakeDB(texts, books)
    return _FakeConnector(db), books


class TestSyncBibleBooksCanonicalShape:
    @pytest.mark.asyncio
    async def test_chapters_sorted_and_shaped_correctly(self):
        """Output preserves the two-stage-$group shape, sorted by chapter."""
        agg_result = [
            {
                "_id": "genesis",
                "chapters": [
                    {"chapter": 2, "verse_count": 25},
                    {"chapter": 1, "verse_count": 31},
                ],
                "total_verses": 56,
            }
        ]
        connector, books = _make_connector(agg_result)

        count = await sync_bible_books_from_texts("english", connector=connector)

        assert count == 1
        assert len(books.update_calls) == 1
        _filter, update_doc, upsert = books.update_calls[0]
        assert upsert is True

        chapters = update_doc["$set"]["chapters"]
        assert chapters == [
            {"chapter": 1, "verse_count": 31},
            {"chapter": 2, "verse_count": 25},
        ]
        assert update_doc["$set"]["total_chapters"] == 2
        assert update_doc["$set"]["total_verses"] == 56

    @pytest.mark.asyncio
    async def test_no_legacy_chapter_number_or_verses(self):
        """Emitted chapter entries must not carry chapter_number or embedded verses."""
        agg_result = [
            {
                "_id": "genesis",
                "chapters": [{"chapter": 1, "verse_count": 31}],
                "total_verses": 31,
            }
        ]
        connector, books = _make_connector(agg_result)

        await sync_bible_books_from_texts("english", connector=connector)

        chapters = books.update_calls[0][1]["$set"]["chapters"]
        for ch in chapters:
            assert "chapter_number" not in ch
            assert "verses" not in ch
            assert set(ch.keys()) == {"chapter", "verse_count"}

    @pytest.mark.asyncio
    async def test_does_not_write_language_name(self):
        """language_name is optional/denormalized — this writer must not set it."""
        agg_result = [
            {
                "_id": "genesis",
                "chapters": [{"chapter": 1, "verse_count": 31}],
                "total_verses": 31,
            }
        ]
        connector, books = _make_connector(agg_result)

        await sync_bible_books_from_texts("kope", connector=connector)

        _filter, update_doc, _upsert = books.update_calls[0]
        assert "language_name" not in update_doc["$set"]
        assert "language_name" not in update_doc.get("$setOnInsert", {})

    @pytest.mark.asyncio
    async def test_multiple_books_each_get_own_update(self):
        """Each grouped book_code produces its own update_one call."""
        agg_result = [
            {
                "_id": "genesis",
                "chapters": [{"chapter": 1, "verse_count": 31}],
                "total_verses": 31,
            },
            {
                "_id": "exodus",
                "chapters": [{"chapter": 1, "verse_count": 22}],
                "total_verses": 22,
            },
        ]
        connector, books = _make_connector(agg_result)

        count = await sync_bible_books_from_texts("english", connector=connector)

        assert count == 2
        assert len(books.update_calls) == 2
        book_codes = {call[0]["book_code"] for call in books.update_calls}
        assert book_codes == {"genesis", "exodus"}

    @pytest.mark.asyncio
    async def test_no_matching_texts_yields_no_updates(self):
        """An empty aggregation result performs zero writes."""
        connector, books = _make_connector([])

        count = await sync_bible_books_from_texts("nonexistent_lang", connector=connector)

        assert count == 0
        assert books.update_calls == []
