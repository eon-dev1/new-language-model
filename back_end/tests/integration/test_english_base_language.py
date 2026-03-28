"""
Integration tests for English base language in database.

These tests verify that English exists in the languages collection
and can be queried via MCP tools. Run against actual MongoDB.

TDD: These tests should FAIL initially, then PASS after running
the seed_english_language.py script.
"""

import pytest


class TestEnglishBaseLanguage:
    """Tests for English as base language in languages collection."""

    @pytest.mark.asyncio
    async def test_english_exists_in_languages_collection(self, db):
        """English should exist in languages collection."""
        languages = db.get_collection("languages")
        english = await languages.find_one({"language_code": "english"})

        assert english is not None, "English not found in languages collection"
        assert english["language_code"] == "english"
        assert english["language_name"] == "English"

    @pytest.mark.asyncio
    async def test_english_is_base_language(self, db):
        """English should have is_base_language=True."""
        languages = db.get_collection("languages")
        english = await languages.find_one({"language_code": "english"})

        assert english is not None, "English not found in languages collection"
        assert english["is_base_language"] is True

    @pytest.mark.asyncio
    async def test_english_has_no_ai_translation_level(self, db):
        """English should have flat translation_stats (no nested human/ai levels)."""
        languages = db.get_collection("languages")
        english = await languages.find_one({"language_code": "english"})

        assert english is not None, "English not found in languages collection"

        assert "translation_stats" in english, "English should have translation_stats"
        assert "translation_levels" not in english, "English should not have old translation_levels"

        stats = english["translation_stats"]
        assert "books_started" in stats, "translation_stats should have books_started"
        assert "verses_translated" in stats, "translation_stats should have verses_translated"

    @pytest.mark.asyncio
    async def test_english_human_translation_has_correct_counts(self, db):
        """English human translation should reflect actual verse counts."""
        languages = db.get_collection("languages")
        english = await languages.find_one({"language_code": "english"})

        assert english is not None, "English not found in languages collection"

        stats = english.get("translation_stats", {})
        verses = stats.get("verses_translated")
        assert 31100 <= verses <= 31200, f"Should have ~31,102 verses, got {verses}"
        assert stats.get("books_started") == 66, "Should have 66 books started"


class TestEnglishMCPToolIntegration:
    """Tests for MCP tools working with English language."""

    @pytest.mark.asyncio
    async def test_validate_language_succeeds_for_english(self, db):
        """validate_language should succeed for English."""
        from mcp_server.tools.base import validate_language

        # Should not raise ToolError
        lang_doc = await validate_language(db, "english")

        assert lang_doc is not None
        assert lang_doc["language_code"] == "english"
        assert lang_doc["is_base_language"] is True

    @pytest.mark.asyncio
    async def test_get_bible_chunk_returns_english_verses(self, db):
        """get_bible_chunk should return English verses from bible_texts."""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(db, "english", limit=5)

        # Should not be an error response
        assert "error" not in result, f"Got error: {result.get('error')}"

        # Should have verses
        assert "verses" in result
        assert len(result["verses"]) > 0, "Should return at least one verse"

        # Verify verse structure
        verse = result["verses"][0]
        assert "text" in verse
        assert "book_code" in verse
        assert len(verse["text"]) > 0, "Verse text should not be empty"

    @pytest.mark.asyncio
    async def test_get_chapter_returns_english_genesis_1(self, db):
        """get_chapter should return Genesis chapter 1 in English."""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(db, "english", "genesis", 1)

        assert "error" not in result, f"Got error: {result.get('error')}"
        assert "verses" in result
        assert result["count"] == 31, "Genesis 1 should have 31 verses"

        # First verse should be "In the beginning..."
        first_verse = result["verses"][0]
        assert first_verse["verse"] == 1
        assert "beginning" in first_verse["text"].lower()

    @pytest.mark.asyncio
    async def test_english_verses_have_no_human_verified_field(self, db):
        """English verses should not include human_verified field."""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(db, "english", "genesis", 1)

        assert "error" not in result
        for verse in result["verses"]:
            assert "human_verified" not in verse, "English verses should not have human_verified"
