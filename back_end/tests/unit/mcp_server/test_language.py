"""
Tests for mcp_server/tools/language.py - Language tools.

TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/mcp_server/test_language.py -v
"""

import pytest


class TestListLanguages:
    """Tests for list_languages tool"""

    @pytest.mark.asyncio
    async def test_list_languages_returns_all(self, mock_mcp_db):
        """Returns all languages in database"""
        from mcp_server.tools.language import list_languages

        result = await list_languages(mock_mcp_db)

        assert "languages" in result
        assert result["count"] == 3  # English, Hebrew, Bughotu
        assert len(result["languages"]) == 3

    @pytest.mark.asyncio
    async def test_list_languages_response_shape(self, mock_mcp_db):
        """Each language has expected fields"""
        from mcp_server.tools.language import list_languages

        result = await list_languages(mock_mcp_db)

        for lang in result["languages"]:
            assert "code" in lang
            assert "name" in lang
            assert "status" in lang
            assert "is_base_language" in lang

    @pytest.mark.asyncio
    async def test_list_languages_includes_progress(self, mock_mcp_db):
        """Languages include translation progress stats"""
        from mcp_server.tools.language import list_languages

        result = await list_languages(mock_mcp_db)

        # Find Hebrew (has both human and ai progress)
        heb = next(l for l in result["languages"] if l["code"] == "heb")
        assert "progress" in heb
        assert "human" in heb["progress"]
        assert "ai" in heb["progress"]

    @pytest.mark.asyncio
    async def test_list_languages_empty_db(self, mock_mcp_db):
        """Returns empty list when no languages"""
        from mcp_server.tools.language import list_languages

        # Clear languages data
        mock_mcp_db._collections_data["languages"] = []

        result = await list_languages(mock_mcp_db)

        assert result["languages"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_list_languages_english_no_ai_progress(self, mock_mcp_db):
        """English only has human progress (no AI)"""
        from mcp_server.tools.language import list_languages

        result = await list_languages(mock_mcp_db)

        english = next(l for l in result["languages"] if l["code"] == "english")
        assert "human" in english["progress"]
        # AI progress should be absent or null for English
        assert english["progress"].get("ai") is None


class TestGetLanguageInfo:
    """Tests for get_language_info tool"""

    @pytest.mark.asyncio
    async def test_get_language_info_exists(self, mock_mcp_db):
        """Returns full language document when found"""
        from mcp_server.tools.language import get_language_info

        result = await get_language_info(mock_mcp_db, "english")

        assert result["language_code"] == "english"
        assert result["language_name"] == "English"
        assert result["is_base_language"] is True

    @pytest.mark.asyncio
    async def test_get_language_info_not_found(self, mock_mcp_db):
        """Returns error when language doesn't exist"""
        from mcp_server.tools.language import get_language_info

        result = await get_language_info(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_language_info_includes_translation_levels(self, mock_mcp_db):
        """Returns translation progress for each level"""
        from mcp_server.tools.language import get_language_info

        result = await get_language_info(mock_mcp_db, "heb")

        assert "translation_levels" in result
        assert "human" in result["translation_levels"]
        assert "books_started" in result["translation_levels"]["human"]

    @pytest.mark.asyncio
    async def test_get_language_info_case_insensitive(self, mock_mcp_db):
        """Handles case variations in language code"""
        from mcp_server.tools.language import get_language_info

        result = await get_language_info(mock_mcp_db, "ENGLISH")

        assert result["language_code"] == "english"

    @pytest.mark.asyncio
    async def test_get_language_info_includes_metadata(self, mock_mcp_db):
        """Returns language metadata"""
        from mcp_server.tools.language import get_language_info

        result = await get_language_info(mock_mcp_db, "heb")

        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_get_language_info_response_excludes_mongo_id(self, mock_mcp_db):
        """Response doesn't include MongoDB _id field"""
        from mcp_server.tools.language import get_language_info

        result = await get_language_info(mock_mcp_db, "english")

        assert "_id" not in result
