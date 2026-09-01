# tests/unit/db_connector/conftest.py
"""
Pytest fixtures for MongoDB db_connector unit tests (no live DB required).

Fixture Dependency Graph:
    mongodb_settings (sync, synthetic — no credential file)
           ↓
    connector (async, unconnected)
"""

import pytest
import pytest_asyncio

from db_connector.settings import MongoDBSettings
from db_connector.connection import MongoDBConnector


# === SETTINGS FIXTURES ===

@pytest.fixture
def mongodb_settings():
    """Synthetic settings for unit tests — no credential file needed."""
    return MongoDBSettings(
        mongodb_connection_string="mongodb://localhost:27019",
        database_name="test_unit",
    )


# === CONNECTOR FIXTURES ===

@pytest_asyncio.fixture
async def connector(mongodb_settings):
    """
    Provide an unconnected MongoDBConnector instance.

    Use this when testing connection establishment itself.
    """
    return MongoDBConnector(mongodb_settings)


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
