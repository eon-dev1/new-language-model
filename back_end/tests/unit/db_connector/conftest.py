# tests/unit/db_connector/conftest.py
"""
Pytest fixtures for MongoDB db_connector tests.

Fixture Dependency Graph:
    mongodb_settings (sync)
           ↓
    connector (async, unconnected)
           ↓
    connected_connector (async, connected with auto-cleanup)
"""

import pytest
import pytest_asyncio
from pathlib import Path

from db_connector.settings import MongoDBSettings
from db_connector.connection import MongoDBConnector


# === SETTINGS FIXTURES ===

@pytest.fixture(scope="module")
def mongodb_settings():
    """
    Load MongoDB settings from the two-tier credential system.

    Module-scoped to avoid repeated credential file reads.
    """
    return MongoDBSettings.create_from_credentials()


@pytest.fixture
def credentials_path_file():
    """Path to the Tier 1 credentials pointer file."""
    return Path(__file__).parent.parent.parent.parent / "db_connector" / "mongo_credentials_path.env"


# === CONNECTOR FIXTURES ===

@pytest_asyncio.fixture
async def connector(mongodb_settings):
    """
    Provide an unconnected MongoDBConnector instance.

    Use this when testing connection establishment itself.
    """
    return MongoDBConnector(mongodb_settings)


@pytest_asyncio.fixture
async def connected_connector(mongodb_settings):
    """
    Provide a connected MongoDBConnector with automatic cleanup.

    Uses yield to ensure disconnect() is called even if test fails.
    This is the primary fixture for tests requiring database access.
    """
    connector = MongoDBConnector(mongodb_settings)
    await connector.connect()
    yield connector
    await connector.disconnect()


# === INVALID SETTINGS FIXTURES ===

@pytest.fixture
def invalid_mongodb_settings():
    """
    Provide settings with an invalid connection string for error testing.

    Uses short timeouts to avoid long waits in tests.
    """
    return MongoDBSettings(
        mongodb_connection_string="mongodb://invalid-host:27017",
        database_name="test_db",
        server_selection_timeout_ms=2000,  # 2 seconds
        connect_timeout_ms=2000,
    )
