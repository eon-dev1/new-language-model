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
    """Test credential loading from ~/.nlm/mongodb_credentials.env."""

    def test_credentials_file_at_home_nlm(self, tmp_path, monkeypatch):
        """Hardcoded path must be Path.home() / '.nlm' / 'mongodb_credentials.env'."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        monkeypatch.delenv("DATABASE_NAME", raising=False)
        nlm_dir = tmp_path / ".nlm"
        nlm_dir.mkdir()
        (nlm_dir / "mongodb_credentials.env").write_text(
            'MONGODB_CONNECTION_STRING="mongodb://localhost:27017"',
            encoding='utf-8',
        )
        settings = MongoDBSettings.create_from_credentials()
        assert settings is not None

    def test_missing_file_raises_with_actionable_message(self, tmp_path, monkeypatch):
        """FileNotFoundError message names the exact expected path."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        with pytest.raises(FileNotFoundError) as exc_info:
            MongoDBSettings.create_from_credentials()
        expected_path = str(tmp_path / ".nlm" / "mongodb_credentials.env")
        assert expected_path in str(exc_info.value)

    def test_missing_connection_string_raises_value_error(self, tmp_path, monkeypatch):
        """File exists but MONGODB_CONNECTION_STRING absent → ValueError."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        nlm_dir = tmp_path / ".nlm"
        nlm_dir.mkdir()
        (nlm_dir / "mongodb_credentials.env").write_text("DATABASE_NAME=foo\n", encoding='utf-8')
        with pytest.raises(ValueError):
            MongoDBSettings.create_from_credentials()

    def test_database_name_omitted_uses_class_default(self, tmp_path, monkeypatch):
        """File without DATABASE_NAME → database_name == 'nlm_translator'."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        monkeypatch.delenv("DATABASE_NAME", raising=False)
        nlm_dir = tmp_path / ".nlm"
        nlm_dir.mkdir()
        (nlm_dir / "mongodb_credentials.env").write_text(
            'MONGODB_CONNECTION_STRING="mongodb://localhost:27017"\n',
            encoding='utf-8',
        )
        settings = MongoDBSettings.create_from_credentials()
        assert settings.database_name == "nlm_translator"

    def test_database_name_in_file_overrides_default(self, tmp_path, monkeypatch):
        """File with DATABASE_NAME=foo → explicit kwarg wins over class default."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        nlm_dir = tmp_path / ".nlm"
        nlm_dir.mkdir()
        (nlm_dir / "mongodb_credentials.env").write_text(
            'MONGODB_CONNECTION_STRING="mongodb://localhost:27017"\nDATABASE_NAME=foo\n',
            encoding='utf-8',
        )
        settings = MongoDBSettings.create_from_credentials()
        assert settings.database_name == "foo"

    def test_parser_tolerates_blank_lines_and_comments(self, tmp_path, monkeypatch):
        """# comment lines and blank lines are skipped; key is still parsed."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        monkeypatch.delenv("DATABASE_NAME", raising=False)
        nlm_dir = tmp_path / ".nlm"
        nlm_dir.mkdir()
        content = (
            "# This is a comment\n"
            "\n"
            'MONGODB_CONNECTION_STRING="mongodb://localhost:27017"\n'
            "\n"
            "# Another comment\n"
        )
        (nlm_dir / "mongodb_credentials.env").write_text(content, encoding='utf-8')
        settings = MongoDBSettings.create_from_credentials()
        assert settings.mongodb_connection_string == "mongodb://localhost:27017"

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
