from unittest.mock import AsyncMock, patch

import pytest

import db_connector.connection as connection_module


@pytest.fixture(autouse=True)
def _reset_global_connector():
    connection_module._global_connector = None
    yield
    connection_module._global_connector = None


@pytest.mark.asyncio
async def test_failed_connect_leaves_global_connector_unset():
    failing_connector = AsyncMock()
    failing_connector.connect.side_effect = ConnectionError("mongod not running")

    with patch.object(connection_module, "MongoDBConnector", return_value=failing_connector):
        with pytest.raises(ConnectionError):
            await connection_module.get_mongodb_connector()

    assert connection_module._global_connector is None


@pytest.mark.asyncio
async def test_get_mongodb_connector_retries_after_a_prior_failure():
    failing_connector = AsyncMock()
    failing_connector.connect.side_effect = ConnectionError("mongod not running")

    with patch.object(connection_module, "MongoDBConnector", return_value=failing_connector):
        with pytest.raises(ConnectionError):
            await connection_module.get_mongodb_connector()

    working_connector = AsyncMock()
    with patch.object(connection_module, "MongoDBConnector", return_value=working_connector):
        result = await connection_module.get_mongodb_connector()

    assert result is working_connector
    assert connection_module._global_connector is working_connector
