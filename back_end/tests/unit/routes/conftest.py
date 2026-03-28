# tests/unit/routes/conftest.py
"""
Pytest fixtures for FastAPI route testing.

Uses httpx AsyncClient with the actual FastAPI app for integration testing.
Tests use the real MongoDB connection to verify end-to-end behavior.

Fixture Dependency Graph:
    mongodb_settings (sync)
           ↓
    connected_db (async, connected with auto-cleanup)
           ↓
    async_client (async, httpx client with app + db override)
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator

from main import app
from db_connector.settings import MongoDBSettings
from db_connector.connection import MongoDBConnector
from routes.dependencies import get_db


# === SETTINGS FIXTURES ===

@pytest.fixture(scope="module")
def mongodb_settings():
    """Load MongoDB settings from the two-tier credential system."""
    return MongoDBSettings.create_from_credentials()


# === DATABASE FIXTURES ===

@pytest_asyncio.fixture
async def connected_db(mongodb_settings) -> AsyncGenerator[MongoDBConnector, None]:
    """
    Provide a connected MongoDBConnector with automatic cleanup.

    Uses yield to ensure disconnect() is called even if test fails.
    """
    connector = MongoDBConnector(mongodb_settings)
    await connector.connect()
    yield connector
    await connector.disconnect()


# === CLIENT FIXTURES ===

@pytest_asyncio.fixture
async def async_client(connected_db) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP client for testing FastAPI routes.

    Overrides the get_db dependency to use our test-scoped connection,
    ensuring consistent database state across test operations.
    """

    async def override_get_db():
        """Override dependency to use test-scoped connection."""
        yield connected_db

    # Override the dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create async client with ASGI transport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clear overrides after test
    app.dependency_overrides.clear()


# === CLEANUP FIXTURES ===

@pytest_asyncio.fixture
async def clean_test_language(connected_db) -> AsyncGenerator[str, None]:
    """
    Provide a unique test language code and clean up after test.

    Removes any documents created during the test from all collections.
    """
    import uuid
    test_language = f"test_lang_{uuid.uuid4().hex[:8]}"

    yield test_language

    # Cleanup: Remove test data from all collections
    database = connected_db.get_database()
    collections = ["dictionaries", "grammar_systems", "bible_texts", "bible_books", "languages"]

    for collection_name in collections:
        collection = database[collection_name]
        await collection.delete_many({"language_code": test_language})
