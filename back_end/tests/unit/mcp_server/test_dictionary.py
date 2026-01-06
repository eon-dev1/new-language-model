"""
Tests for mcp_server/tools/dictionary.py - Dictionary tools.

TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/mcp_server/test_dictionary.py -v

Note: Dictionary uses embedded entries[] array pattern.
One doc per (language, translation_type) with entries embedded.
"""

import pytest


class TestListDictionaryEntries:
    """Tests for list_dictionary_entries tool"""

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_returns_entries(self, mock_mcp_db):
        """Returns entries for a language"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb")

        assert "entries" in result
        assert "total" in result
        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_response_shape(self, mock_mcp_db):
        """Each entry has expected fields"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb")

        for entry in result["entries"]:
            assert "word" in entry
            assert "definition" in entry
            assert "part_of_speech" in entry

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_with_translation_type(self, mock_mcp_db):
        """Filters by translation type when specified"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(
            mock_mcp_db, "heb", translation_type="human"
        )

        assert "entries" in result

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_pagination(self, mock_mcp_db):
        """Supports offset and limit for pagination"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        # Get all entries
        all_result = await list_dictionary_entries(mock_mcp_db, "heb")

        # Get with limit
        limited = await list_dictionary_entries(mock_mcp_db, "heb", limit=1)

        assert len(limited["entries"]) <= 1
        assert limited["offset"] == 0
        assert limited["limit"] == 1

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_offset(self, mock_mcp_db):
        """Offset skips entries"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        first = await list_dictionary_entries(mock_mcp_db, "heb", offset=0, limit=1)
        second = await list_dictionary_entries(mock_mcp_db, "heb", offset=1, limit=1)

        if first["entries"] and second["entries"]:
            assert first["entries"][0]["word"] != second["entries"][0]["word"]

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_empty_dictionary(self, mock_mcp_db):
        """Returns empty list for language with no entries"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        # English exists but has no dictionary in test data
        result = await list_dictionary_entries(mock_mcp_db, "english")

        assert result["entries"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_with_search(self, mock_mcp_db):
        """Filters entries by search term"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb", search="beginning")

        # Should find entry with "beginning" in definition
        if result["entries"]:
            assert any("beginning" in e["definition"].lower() for e in result["entries"])


class TestGetDictionaryEntry:
    """Tests for get_dictionary_entry tool"""

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_exists(self, mock_mcp_db):
        """Returns entry when word exists"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "בראשית")

        assert "word" in result
        assert result["word"] == "בראשית"
        assert "definition" in result

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_not_found(self, mock_mcp_db):
        """Returns error when word doesn't exist"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "nonexistent_word")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_with_translation_type(self, mock_mcp_db):
        """Filters by translation type when specified"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(
            mock_mcp_db, "heb", "בראשית", translation_type="human"
        )

        assert "word" in result

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "nonexistent", "word")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_includes_examples(self, mock_mcp_db):
        """Entry includes examples field"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "בראשית")

        assert "examples" in result


class TestUpsertDictionaryEntries:
    """Tests for upsert_dictionary_entries tool"""

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_insert_new(self, mock_mcp_db):
        """Inserts new entries"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        new_entries = [
            {
                "word": "חדש",
                "definition": "new",
                "part_of_speech": "adjective",
            }
        ]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", "human", new_entries
        )

        assert result["created"] >= 1
        assert "total" in result

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_update_existing(self, mock_mcp_db):
        """Updates existing entries"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        # Update existing word with new definition
        entries = [
            {
                "word": "בראשית",
                "definition": "In the very beginning",
                "part_of_speech": "noun",
            }
        ]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", "human", entries
        )

        assert result["updated"] >= 1

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_mixed(self, mock_mcp_db):
        """Handles mix of inserts and updates"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [
            {"word": "בראשית", "definition": "Updated def", "part_of_speech": "noun"},
            {"word": "חדש", "definition": "new word", "part_of_speech": "adjective"},
        ]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", "human", entries
        )

        assert result["created"] + result["updated"] == 2

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_returns_counts(self, mock_mcp_db):
        """Returns created/updated/total counts"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "test", "definition": "test def", "part_of_speech": "noun"}]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", "human", entries
        )

        assert "created" in result
        assert "updated" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_empty_array(self, mock_mcp_db):
        """Handles empty entries array"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        result = await upsert_dictionary_entries(mock_mcp_db, "heb", "human", [])

        assert result["created"] == 0
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "test", "definition": "test", "part_of_speech": "noun"}]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "nonexistent", "human", entries
        )

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_requires_translation_type(self, mock_mcp_db):
        """Requires translation_type for writes"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "test", "definition": "test", "part_of_speech": "noun"}]

        # translation_type is required, None should error
        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", None, entries  # type: ignore
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_validates_entries(self, mock_mcp_db):
        """Validates entry structure"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        # Missing required field 'definition'
        entries = [{"word": "test", "part_of_speech": "noun"}]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", "human", entries
        )

        assert "error" in result
        assert result["error"]["code"] == "validation_error"
