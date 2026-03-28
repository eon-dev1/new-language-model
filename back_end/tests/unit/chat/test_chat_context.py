"""
Tests for utils/chat_context.py

Failure points targeted:
- No language_code → empty string (not crash)
- DB document missing expected keys → graceful handling
- Context truncation at MAX_CONTEXT_CHARS
- Unknown view type → just returns language metadata
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.chat_context import assemble_context, MAX_CONTEXT_CHARS


def _make_mock_db(collections=None):
    """Create a mock DB with configurable collection responses."""
    collections = collections or {}
    db = MagicMock()

    def get_collection(name):
        coll = AsyncMock()
        if name in collections:
            setup = collections[name]
            if "find_one" in setup:
                coll.find_one = AsyncMock(return_value=setup["find_one"])
            if "find" in setup:
                cursor = AsyncMock()
                cursor.sort = MagicMock(return_value=cursor)
                cursor.to_list = AsyncMock(return_value=setup["find"])
                coll.find = MagicMock(return_value=cursor)
        else:
            coll.find_one = AsyncMock(return_value=None)
            cursor = AsyncMock()
            cursor.sort = MagicMock(return_value=cursor)
            cursor.to_list = AsyncMock(return_value=[])
            coll.find = MagicMock(return_value=cursor)
        return coll

    db.get_collection = get_collection
    return db


class TestAssembleContext:
    @pytest.mark.asyncio
    async def test_no_language_returns_empty(self):
        result = await assemble_context(MagicMock(), language_code=None)
        assert result == ""

    @pytest.mark.asyncio
    async def test_language_not_found_returns_empty(self):
        db = _make_mock_db()
        result = await assemble_context(db, language_code="nonexistent")
        assert result == ""

    @pytest.mark.asyncio
    async def test_language_metadata_basic(self):
        db = _make_mock_db({
            "languages": {
                "find_one": {
                    "language_code": "bughotu",
                    "language_name": "Bughotu",
                    "status": "active",
                    "translation_levels": {},
                }
            }
        })
        result = await assemble_context(db, language_code="bughotu")
        assert "Bughotu" in result
        assert "active" in result

    @pytest.mark.asyncio
    async def test_missing_keys_in_language_doc(self):
        """DB doc might be missing language_name, status, etc."""
        db = _make_mock_db({
            "languages": {
                "find_one": {"language_code": "test"}
                # No language_name, no status, no translation_levels
            }
        })
        result = await assemble_context(db, language_code="test")
        assert "test" in result  # Falls back to language_code
        assert "unknown" in result  # Default status

    @pytest.mark.asyncio
    async def test_unknown_view_returns_just_metadata(self):
        db = _make_mock_db({
            "languages": {
                "find_one": {
                    "language_code": "test",
                    "language_name": "Test",
                    "status": "active",
                    "translation_levels": {},
                }
            }
        })
        result = await assemble_context(db, language_code="test", view="some_unknown_view")
        assert "Test" in result
        # Should NOT crash, just returns language metadata

    @pytest.mark.asyncio
    async def test_context_truncation(self):
        """Context exceeding MAX_CONTEXT_CHARS gets truncated."""
        huge_name = "A" * (MAX_CONTEXT_CHARS + 1000)
        db = _make_mock_db({
            "languages": {
                "find_one": {
                    "language_code": "test",
                    "language_name": huge_name,
                    "status": "active",
                    "translation_levels": {},
                }
            }
        })
        result = await assemble_context(db, language_code="test")
        assert len(result) <= MAX_CONTEXT_CHARS + 100  # Allow for truncation message
        assert "[Context truncated" in result

    @pytest.mark.asyncio
    async def test_bible_context_with_missing_translations(self):
        """English verses exist but target language has none."""
        english_verses = [
            {"verse": 1, "text": "In the beginning"},
            {"verse": 2, "text": "And the earth was"},
        ]

        lang_coll = AsyncMock()
        lang_coll.find_one = AsyncMock(return_value={
            "language_code": "test",
            "language_name": "Test",
            "status": "active",
            "translation_levels": {},
        })

        # bible_texts.find() is called twice: once for English, once for target.
        # We need different results based on query filter.
        call_count = 0
        def bible_find(query):
            nonlocal call_count
            call_count += 1
            cursor = AsyncMock()
            cursor.sort = MagicMock(return_value=cursor)
            if call_count == 1:  # English query
                cursor.to_list = AsyncMock(return_value=english_verses)
            else:  # Target language query
                cursor.to_list = AsyncMock(return_value=[])
            return cursor

        bible_coll = MagicMock()
        bible_coll.find = bible_find

        db = MagicMock()
        db.get_collection = lambda name: lang_coll if name == "languages" else bible_coll

        result = await assemble_context(
            db, language_code="test", book_code="genesis", chapter=1, view="bible_reader"
        )
        assert "not yet translated" in result

    @pytest.mark.asyncio
    async def test_dictionary_empty_entries(self):
        db = _make_mock_db({
            "languages": {
                "find_one": {
                    "language_code": "test",
                    "language_name": "Test",
                    "status": "active",
                    "translation_levels": {},
                }
            },
            "dictionaries": {
                "find_one": {
                    "language_code": "test",
                    "human": [],
                    "ai": [],
                }
            },
        })
        result = await assemble_context(db, language_code="test", view="dictionary")
        # Should return just language metadata, no dictionary section
        assert "Dictionary" not in result
