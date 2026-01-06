"""
Tests for mcp_server/server.py - Server integration tests.

TDD: These tests verify the MCP server setup and tool registration.
Run with: pytest tests/unit/mcp_server/test_integration.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestServerSetup:
    """Tests for MCP server initialization"""

    def test_server_creates_mcp_instance(self):
        """Server module creates FastMCP instance"""
        from mcp_server.server import mcp

        assert mcp is not None
        assert mcp.name == "nlm-database"

    def test_server_has_correct_name(self):
        """Server is named 'nlm-database'"""
        from mcp_server.server import mcp

        assert mcp.name == "nlm-database"


class TestToolRegistration:
    """Tests for tool registration"""

    def test_all_tools_registered(self):
        """All 13 tools are registered"""
        from mcp_server.server import mcp

        # Get registered tools
        tools = mcp._tool_manager._tools

        expected_tools = {
            "list_languages",
            "get_language_info",
            "list_bible_books",
            "get_chapter",
            "get_bible_chunk",
            "save_bible_batches",
            "get_parallel_verses",
            "list_dictionary_entries",
            "get_dictionary_entry",
            "upsert_dictionary_entries",
            "list_grammar_categories",
            "get_grammar_category",
            "update_grammar_category",
        }

        registered_names = set(tools.keys())
        assert expected_tools == registered_names, f"Missing: {expected_tools - registered_names}"

    def test_tools_have_descriptions(self):
        """Each tool has a description"""
        from mcp_server.server import mcp

        tools = mcp._tool_manager._tools

        for name, tool in tools.items():
            assert tool.description, f"Tool {name} missing description"

    def test_language_tools_registered(self):
        """Language tools are registered"""
        from mcp_server.server import mcp

        tools = mcp._tool_manager._tools
        assert "list_languages" in tools
        assert "get_language_info" in tools

    def test_bible_tools_registered(self):
        """Bible tools are registered"""
        from mcp_server.server import mcp

        tools = mcp._tool_manager._tools
        assert "list_bible_books" in tools
        assert "get_chapter" in tools
        assert "get_bible_chunk" in tools

    def test_dictionary_tools_registered(self):
        """Dictionary tools are registered"""
        from mcp_server.server import mcp

        tools = mcp._tool_manager._tools
        assert "list_dictionary_entries" in tools
        assert "get_dictionary_entry" in tools
        assert "upsert_dictionary_entries" in tools

    def test_grammar_tools_registered(self):
        """Grammar tools are registered"""
        from mcp_server.server import mcp

        tools = mcp._tool_manager._tools
        assert "list_grammar_categories" in tools
        assert "get_grammar_category" in tools
        assert "update_grammar_category" in tools


class TestToolSchemas:
    """Tests for tool input schemas"""

    def test_list_languages_no_required_params(self):
        """list_languages has no required parameters"""
        from mcp_server.server import mcp

        tool = mcp._tool_manager._tools["list_languages"]
        # Should have empty or optional params only
        schema = tool.parameters
        required = schema.get("required", [])
        assert len(required) == 0

    def test_get_language_info_requires_language_code(self):
        """get_language_info requires language_code"""
        from mcp_server.server import mcp

        tool = mcp._tool_manager._tools["get_language_info"]
        schema = tool.parameters
        required = schema.get("required", [])
        assert "language_code" in required

    def test_get_chapter_requires_params(self):
        """get_chapter requires language_code, book_code, chapter"""
        from mcp_server.server import mcp

        tool = mcp._tool_manager._tools["get_chapter"]
        schema = tool.parameters
        required = schema.get("required", [])
        assert "language_code" in required
        assert "book_code" in required
        assert "chapter" in required


class TestDatabaseConnection:
    """Tests for database connection handling"""

    def test_get_db_function_exists(self):
        """get_db function exists for dependency injection"""
        from mcp_server.server import get_db

        assert callable(get_db)

    @pytest.mark.asyncio
    async def test_get_db_returns_connector(self):
        """get_db returns MongoDBConnector instance"""
        from mcp_server.server import get_db

        db = await get_db()
        assert db is not None
        # Should have get_collection method
        assert hasattr(db, "get_collection")
