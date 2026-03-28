# tests/unit/db_connector/test_mongodb_connection.py
"""
MongoDB Connection Unit Tests

Tests that require NO live database connection.
Tests requiring a real MongoDB instance live in tests/integration/test_mongodb_connection.py.

Test Categories:
    1. Settings Loading - Credential system validation
    2. Connection Establishment - Pre-connection state only
    3. Error Handling - Invalid settings, uninitialized state
"""

from pathlib import Path

import pytest

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
    """Test MongoDB connection initial state (no live DB required)."""

    @pytest.mark.asyncio
    async def test_is_connected_before_connect(self, connector):
        """Connector should report not connected before connect() called."""
        assert not connector.is_connected


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error conditions that don't require a live database."""

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
