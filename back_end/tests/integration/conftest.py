"""Fixtures for integration tests."""

import pytest
import pytest_asyncio
from db_connector.settings import MongoDBSettings
from db_connector.connection import MongoDBConnector

@pytest_asyncio.fixture
async def db():
    """Real MongoDB connection for integration tests, with cleanup."""
    connector = MongoDBConnector()
    await connector.connect()
    yield connector
    await connector.disconnect()


@pytest.fixture(scope="module")
def mongodb_settings():
    """Load MongoDB settings from the two-tier credential system."""
    return MongoDBSettings.create_from_credentials()


@pytest.fixture
def invalid_mongodb_settings():
    """Settings with an invalid connection string for error testing."""
    return MongoDBSettings(
        mongodb_connection_string="mongodb://invalid-host:27017",
        database_name="test_db",
        server_selection_timeout_ms=2000,
        connect_timeout_ms=2000,
    )


@pytest_asyncio.fixture
async def connector(mongodb_settings):
    """Unconnected MongoDBConnector for testing connection establishment."""
    return MongoDBConnector(mongodb_settings)


@pytest_asyncio.fixture
async def connected_connector(mongodb_settings):
    """Connected MongoDBConnector with automatic cleanup."""
    connector = MongoDBConnector(mongodb_settings)
    await connector.connect()
    yield connector
    await connector.disconnect()
