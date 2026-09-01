"""
Integration tests for mcp_server/server.py - live database wiring.

Tests that require a live MongoDB instance on 127.0.0.1:27019.
"""

import pytest

pytestmark = pytest.mark.integration


class TestDatabaseConnection:
    """Tests for database connection handling"""

    @pytest.mark.asyncio
    async def test_get_db_returns_connector(self):
        """get_db returns MongoDBConnector instance"""
        from mcp_server.server import get_db

        db = await get_db()
        assert db is not None
        # Should have get_collection method
        assert hasattr(db, "get_collection")
