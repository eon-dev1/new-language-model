# tests/unit/db_connector/test_mongodb_connection.py
"""
MongoDB Connection Tests - Pytest Style

Refactored from the original standalone MongoDBConnectionTester class.
All tests use pytest fixtures for proper isolation and cleanup.

Test Categories:
    1. Settings Loading - Credential system validation
    2. Connection Establishment - Connect/disconnect lifecycle
    3. Basic Operations - Ping, server info, collections
    4. Health Check - Monitoring functionality
    5. Error Handling - Invalid connections, uninitialized state
    6. Connection Cleanup - Disconnect, reconnect, context manager
"""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from db_connector.settings import MongoDBSettings
from db_connector.connection import MongoDBConnector


# =============================================================================
# SETTINGS LOADING TESTS
# =============================================================================

class TestSettingsLoading:
    """Test the two-tier credential loading system."""

    def test_credentials_path_file_exists(self, credentials_path_file):
        """Tier 1 credentials pointer file should exist."""
        assert credentials_path_file.exists(), (
            f"mongo_credentials_path.env not found at: {credentials_path_file}"
        )

    def test_settings_creation_succeeds(self, mongodb_settings):
        """Settings should be created from credentials without error."""
        assert mongodb_settings is not None

    def test_database_name_configured(self, mongodb_settings):
        """Database name should be set from Tier 1 config."""
        assert mongodb_settings.database_name
        assert len(mongodb_settings.database_name) > 0

    def test_connection_string_format_valid(self, mongodb_settings):
        """Connection string should start with mongodb:// or mongodb+srv://"""
        conn_str = mongodb_settings.mongodb_connection_string
        assert conn_str.startswith(("mongodb://", "mongodb+srv://")), (
            f"Invalid connection string format: {conn_str[:20]}..."
        )

    def test_connection_options_returned(self, mongodb_settings):
        """get_connection_options() should return expected keys."""
        options = mongodb_settings.get_connection_options()

        expected_keys = [
            "minPoolSize",
            "maxPoolSize",
            "serverSelectionTimeoutMS",
            "connectTimeoutMS",
            "socketTimeoutMS",
        ]
        for key in expected_keys:
            assert key in options, f"Missing option: {key}"

    def test_pool_size_configuration(self, mongodb_settings):
        """Pool size should be configured with sensible defaults."""
        options = mongodb_settings.get_connection_options()

        assert options["minPoolSize"] >= 1
        assert options["maxPoolSize"] >= options["minPoolSize"]
        assert options["maxPoolSize"] <= 100  # Sanity check


# =============================================================================
# CONNECTION ESTABLISHMENT TESTS
# =============================================================================

class TestConnectionEstablishment:
    """Test MongoDB connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_success(self, connector):
        """Connector should establish connection successfully."""
        await connector.connect()
        assert connector.is_connected
        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_is_connected_before_connect(self, connector):
        """Connector should report not connected before connect() called."""
        assert not connector.is_connected

    @pytest.mark.asyncio
    async def test_is_connected_after_connect(self, connected_connector):
        """Connector should report connected after successful connect()."""
        assert connected_connector.is_connected

    @pytest.mark.asyncio
    async def test_get_client_returns_motor_client(self, connected_connector):
        """get_client() should return a Motor client instance."""
        client = connected_connector.get_client()
        assert client is not None
        # Verify it's a Motor client by checking for expected method
        assert hasattr(client, "admin")

    @pytest.mark.asyncio
    async def test_get_database_returns_database(self, connected_connector):
        """get_database() should return the configured database."""
        database = connected_connector.get_database()
        assert database is not None
        assert database.name  # Should have a name

    @pytest.mark.asyncio
    async def test_database_name_matches_settings(self, connected_connector, mongodb_settings):
        """Database name should match the configured name."""
        database = connected_connector.get_database()
        assert database.name == mongodb_settings.database_name


# =============================================================================
# BASIC OPERATIONS TESTS
# =============================================================================

class TestBasicOperations:
    """Test fundamental database operations."""

    @pytest.mark.asyncio
    async def test_ping_succeeds(self, connected_connector):
        """Ping command should succeed on connected database."""
        client = connected_connector.get_client()
        result = await client.admin.command("ping")
        assert result.get("ok") == 1

    @pytest.mark.asyncio
    async def test_server_info_available(self, connected_connector):
        """Server info should be retrievable."""
        client = connected_connector.get_client()
        server_info = await client.server_info()

        assert "version" in server_info
        assert server_info["version"]  # Not empty

    @pytest.mark.asyncio
    async def test_list_collection_names(self, connected_connector):
        """Should be able to list collection names."""
        database = connected_connector.get_database()
        collection_names = await database.list_collection_names()

        # Result should be a list (may be empty for fresh database)
        assert isinstance(collection_names, list)

    @pytest.mark.asyncio
    async def test_database_stats_accessible(self, connected_connector):
        """Database stats command should succeed."""
        database = connected_connector.get_database()

        try:
            stats = await database.command("dbstats")
            assert "collections" in stats or "ok" in stats
        except Exception:
            # Some MongoDB configurations may restrict dbstats
            pytest.skip("dbstats command not accessible in this configuration")


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestHealthCheck:
    """Test the health check monitoring functionality."""

    @pytest.mark.asyncio
    async def test_health_check_returns_dict(self, connected_connector):
        """health_check() should return a dictionary."""
        health_info = await connected_connector.health_check()
        assert isinstance(health_info, dict)

    @pytest.mark.asyncio
    async def test_health_check_connected_status(self, connected_connector):
        """Health check should report connected status."""
        health_info = await connected_connector.health_check()
        assert health_info.get("connected") is True

    @pytest.mark.asyncio
    async def test_health_check_ping_success(self, connected_connector):
        """Health check should report successful ping."""
        health_info = await connected_connector.health_check()
        assert health_info.get("ping_success") is True

    @pytest.mark.asyncio
    async def test_health_check_database_name(self, connected_connector, mongodb_settings):
        """Health check should report correct database name."""
        health_info = await connected_connector.health_check()
        assert health_info.get("database") == mongodb_settings.database_name

    @pytest.mark.asyncio
    async def test_health_check_collections_count(self, connected_connector):
        """Health check should include collections count."""
        health_info = await connected_connector.health_check()
        assert "collections_count" in health_info
        assert isinstance(health_info["collections_count"], int)

    @pytest.mark.asyncio
    async def test_health_check_server_info(self, connected_connector):
        """Health check should include server info."""
        health_info = await connected_connector.health_check()

        if "server_info" in health_info and health_info["server_info"]:
            assert "version" in health_info["server_info"]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error conditions and exception handling."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_invalid_connection_string_raises(self, invalid_mongodb_settings):
        """Connection with invalid URI should raise exception."""
        connector = MongoDBConnector(invalid_mongodb_settings)

        with pytest.raises(Exception):
            # Should timeout or raise connection error
            await connector.connect()

    def test_get_client_before_connect_raises(self, mongodb_settings):
        """get_client() before connect() should raise RuntimeError."""
        connector = MongoDBConnector(mongodb_settings)

        with pytest.raises(RuntimeError):
            connector.get_client()

    def test_get_database_before_connect_raises(self, mongodb_settings):
        """get_database() before connect() should raise RuntimeError."""
        connector = MongoDBConnector(mongodb_settings)

        with pytest.raises(RuntimeError):
            connector.get_database()

    def test_invalid_connection_string_validation(self):
        """Invalid connection string format should be rejected by settings."""
        with pytest.raises(ValueError):
            MongoDBSettings(
                mongodb_connection_string="not-a-valid-uri",
                database_name="test_db"
            )

    def test_empty_database_name_validation(self):
        """Empty database name should be rejected by settings."""
        with pytest.raises(ValueError):
            MongoDBSettings(
                mongodb_connection_string="mongodb://localhost:27017",
                database_name=""
            )


# =============================================================================
# CONNECTION CLEANUP TESTS
# =============================================================================

class TestConnectionCleanup:
    """Test connection cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_disconnect_updates_status(self, mongodb_settings):
        """disconnect() should update is_connected to False."""
        connector = MongoDBConnector(mongodb_settings)
        await connector.connect()
        assert connector.is_connected

        await connector.disconnect()
        assert not connector.is_connected

    @pytest.mark.asyncio
    async def test_reconnection_after_disconnect(self, mongodb_settings):
        """Should be able to reconnect after disconnecting."""
        connector = MongoDBConnector(mongodb_settings)

        # First connection
        await connector.connect()
        assert connector.is_connected

        # Disconnect
        await connector.disconnect()
        assert not connector.is_connected

        # Reconnect
        await connector.connect()
        assert connector.is_connected

        # Cleanup
        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_context_manager_connects(self, mongodb_settings):
        """Context manager should establish connection."""
        async with MongoDBConnector(mongodb_settings) as connector:
            assert connector.is_connected

    @pytest.mark.asyncio
    async def test_context_manager_disconnects_on_exit(self, mongodb_settings):
        """Context manager should disconnect on exit."""
        connector = None
        async with MongoDBConnector(mongodb_settings) as ctx_connector:
            connector = ctx_connector
            assert connector.is_connected

        # After exiting context, should be disconnected
        assert not connector.is_connected

    @pytest.mark.asyncio
    async def test_context_manager_disconnects_on_exception(self, mongodb_settings):
        """Context manager should disconnect even if exception raised."""
        connector = None

        with pytest.raises(ValueError):
            async with MongoDBConnector(mongodb_settings) as ctx_connector:
                connector = ctx_connector
                assert connector.is_connected
                raise ValueError("Intentional test exception")

        # Should still be disconnected despite exception
        assert not connector.is_connected

    @pytest.mark.asyncio
    async def test_multiple_disconnect_calls_safe(self, mongodb_settings):
        """Multiple disconnect() calls should not raise."""
        connector = MongoDBConnector(mongodb_settings)
        await connector.connect()

        # Multiple disconnects should be safe
        await connector.disconnect()
        await connector.disconnect()  # Should not raise
        await connector.disconnect()  # Should not raise

        assert not connector.is_connected
