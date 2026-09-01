"""Pytest fixtures for migration script tests — requires a live MongoDB."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator

from db_connector.settings import MongoDBSettings
from db_connector.connection import MongoDBConnector
from db_connector import connection as conn_mod


@pytest.fixture(scope="module")
def mongodb_settings():
    return MongoDBSettings.create_from_credentials()


@pytest_asyncio.fixture
async def connected_db(mongodb_settings) -> AsyncGenerator[MongoDBConnector, None]:
    """
    Provide a fresh, connected MongoDBConnector with automatic cleanup.

    Also resets the module-global `_global_connector` so the migration's
    `get_mongodb_connector()` builds a fresh connector inside THIS test's
    event loop. Without the reset, the previous test's closed connector
    leaks across and the migration scan hits `RuntimeError: Event loop is closed`.
    """
    conn_mod._global_connector = None
    connector = MongoDBConnector(mongodb_settings)
    await connector.connect()
    yield connector
    await connector.disconnect()
    # If the migration created a global, close it too so the next test starts clean.
    if conn_mod._global_connector is not None:
        try:
            await conn_mod._global_connector.disconnect()
        except Exception:
            pass
        conn_mod._global_connector = None
