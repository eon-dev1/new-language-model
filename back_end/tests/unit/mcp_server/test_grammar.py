"""
Tests for mcp_server/tools/grammar.py - Grammar tools.

TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/mcp_server/test_grammar.py -v

Note: Grammar uses nested categories{} pattern.
One doc per (language, translation_type) with 5 categories:
phonology, morphology, syntax, semantics, discourse
"""

import pytest

VALID_CATEGORIES = ["phonology", "morphology", "syntax", "semantics", "discourse"]


class TestListGrammarCategories:
    """Tests for list_grammar_categories tool"""

    @pytest.mark.asyncio
    async def test_list_grammar_categories_returns_five(self, mock_mcp_db):
        """Returns all 5 grammar categories"""
        from mcp_server.tools.grammar import list_grammar_categories

        result = await list_grammar_categories(mock_mcp_db, "heb")

        assert "categories" in result
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_list_grammar_categories_response_shape(self, mock_mcp_db):
        """Each category has expected fields"""
        from mcp_server.tools.grammar import list_grammar_categories

        result = await list_grammar_categories(mock_mcp_db, "heb")

        for cat in result["categories"]:
            assert "name" in cat
            assert "has_content" in cat
            assert cat["name"] in VALID_CATEGORIES

    @pytest.mark.asyncio
    async def test_list_grammar_categories_shows_content_status(self, mock_mcp_db):
        """has_content reflects whether category has notes/examples"""
        from mcp_server.tools.grammar import list_grammar_categories

        result = await list_grammar_categories(mock_mcp_db, "heb")

        # phonology has content in test data
        phonology = next(c for c in result["categories"] if c["name"] == "phonology")
        assert phonology["has_content"] is True

        # syntax is empty in test data
        syntax = next(c for c in result["categories"] if c["name"] == "syntax")
        assert syntax["has_content"] is False

    @pytest.mark.asyncio
    async def test_list_grammar_categories_returns_categories_for_language(self, mock_mcp_db):
        """Returns categories for the language"""
        from mcp_server.tools.grammar import list_grammar_categories

        result = await list_grammar_categories(mock_mcp_db, "heb")

        assert "categories" in result

    @pytest.mark.asyncio
    async def test_list_grammar_categories_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.grammar import list_grammar_categories

        result = await list_grammar_categories(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_grammar_categories_no_grammar_system(self, mock_mcp_db):
        """Returns empty categories for language with no grammar system"""
        from mcp_server.tools.grammar import list_grammar_categories

        # English exists but has no grammar system in test data
        result = await list_grammar_categories(mock_mcp_db, "english")

        assert result["categories"] == []
        assert result["count"] == 0


class TestGetGrammarCategory:
    """Tests for get_grammar_category tool"""

    @pytest.mark.asyncio
    async def test_get_grammar_category_exists(self, mock_mcp_db):
        """Returns category content when found"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "heb", "phonology")

        assert "description" in result
        assert "notes" in result
        assert "examples" in result
        assert "subcategories" in result

    @pytest.mark.asyncio
    async def test_get_grammar_category_with_content(self, mock_mcp_db):
        """Returns populated category data"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "heb", "phonology")

        # phonology has content in test data
        assert len(result["notes"]) > 0
        assert "Hebrew" in result["description"]

    @pytest.mark.asyncio
    async def test_get_grammar_category_empty(self, mock_mcp_db):
        """Returns empty arrays for category without content"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "heb", "syntax")

        assert result["notes"] == []
        assert result["examples"] == []

    @pytest.mark.asyncio
    async def test_get_grammar_category_invalid_name(self, mock_mcp_db):
        """Returns error for invalid category name"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "heb", "invalid_category")

        assert "error" in result
        assert result["error"]["code"] == "invalid_category"

    @pytest.mark.asyncio
    async def test_get_grammar_category_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "nonexistent", "phonology")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_grammar_category_returns_description(self, mock_mcp_db):
        """Returns description field for category"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "heb", "phonology")

        assert "description" in result

    @pytest.mark.asyncio
    async def test_get_grammar_category_includes_name(self, mock_mcp_db):
        """Response includes category name"""
        from mcp_server.tools.grammar import get_grammar_category

        result = await get_grammar_category(mock_mcp_db, "heb", "morphology")

        assert result.get("name") == "morphology"


class TestUpdateGrammarCategory:
    """Tests for update_grammar_category tool"""

    @pytest.mark.asyncio
    async def test_update_grammar_category_success(self, mock_mcp_db):
        """Updates category content"""
        from mcp_server.tools.grammar import update_grammar_category

        content = {
            "description": "Updated phonology description",
            "notes": ["New note about consonants"],
        }

        result = await update_grammar_category(
            mock_mcp_db, "heb", "phonology", content
        )

        assert result["success"] is True
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_update_grammar_category_partial_update(self, mock_mcp_db):
        """Can update individual fields without replacing all"""
        from mcp_server.tools.grammar import update_grammar_category

        # Just update notes, leave everything else
        content = {"notes": ["Just adding a note"]}

        result = await update_grammar_category(
            mock_mcp_db, "heb", "morphology", content
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_grammar_category_invalid_name(self, mock_mcp_db):
        """Returns error for invalid category name"""
        from mcp_server.tools.grammar import update_grammar_category

        result = await update_grammar_category(
            mock_mcp_db, "heb", "invalid_category", {"notes": []}
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_category"

    @pytest.mark.asyncio
    async def test_update_grammar_category_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.grammar import update_grammar_category

        result = await update_grammar_category(
            mock_mcp_db, "nonexistent", "phonology", {"notes": []}
        )

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_update_grammar_category_creates_if_missing(self, mock_mcp_db):
        """Creates grammar system if it doesn't exist"""
        from mcp_server.tools.grammar import update_grammar_category

        # English has no grammar system in test data
        result = await update_grammar_category(
            mock_mcp_db,
            "english",
            "phonology",
            {"description": "English phonology", "notes": ["44 phonemes"]},
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_grammar_category_validates_content_fields(self, mock_mcp_db):
        """Only allows valid category fields"""
        from mcp_server.tools.grammar import update_grammar_category

        # Invalid field
        content = {"invalid_field": "should not be allowed"}

        result = await update_grammar_category(
            mock_mcp_db, "heb", "phonology", content
        )

        # Should either ignore invalid fields or return validation error
        # Implementation can choose - just shouldn't crash
        assert "success" in result or "error" in result

    @pytest.mark.asyncio
    async def test_update_rejects_wrong_type_description(self, mock_mcp_db):
        """description must be a string, not a number."""
        from mcp_server.tools.grammar import update_grammar_category
        content = {"description": 99999}
        result = await update_grammar_category(mock_mcp_db, "heb", "phonology", content)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_rejects_extra_fields(self, mock_mcp_db):
        """Unknown fields are rejected (extra='forbid')."""
        from mcp_server.tools.grammar import update_grammar_category
        content = {"description": "ok", "malicious_field": "injected"}
        result = await update_grammar_category(mock_mcp_db, "heb", "phonology", content)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_still_accepts_valid_content(self, mock_mcp_db):
        """Regression: normal grammar updates still accepted after validation."""
        from mcp_server.tools.grammar import update_grammar_category
        content = {"description": "Updated phonology", "notes": ["vowel harmony observed"]}
        result = await update_grammar_category(mock_mcp_db, "heb", "phonology", content)
        assert result.get("success") is True
