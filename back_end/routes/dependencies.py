# routes/dependencies.py
"""
FastAPI dependency injection and utilities for routes.

Provides request-scoped MongoDB connections and error handling utilities.
"""

import logging
from typing import AsyncGenerator
from fastapi import HTTPException
from db_connector.connection import MongoDBConnector
from db_connector.settings import MongoDBSettings

logger = logging.getLogger(__name__)


def api_error(operation: str, e: Exception, status: int = 500) -> HTTPException:
    """
    Create a standardized API error response.

    Logs the full exception details server-side while returning
    a clean error message to the client.

    Args:
        operation: Description of the failed operation (e.g., "retrieve languages")
        e: The exception that occurred
        status: HTTP status code (default 500)

    Returns:
        HTTPException ready to be raised
    """
    # exc_info=e, not logger.exception(): the exception is a parameter here, not
    # ambient. logger.exception() reads sys.exc_info(), which is only populated
    # inside an except block — a caller outside one would silently log
    # "NoneType: None" and lose the traceback.
    logger.error(f"{operation} failed", exc_info=e)
    return HTTPException(status_code=status, detail=f"{operation} failed")


async def get_db() -> AsyncGenerator[MongoDBConnector, None]:
    """
    FastAPI dependency for MongoDB connection lifecycle.

    Provides a connected MongoDBConnector instance for the duration of a request,
    automatically disconnecting when the request completes.

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(db: MongoDBConnector = Depends(get_db)):
            database = db.get_database()
            ...

    Yields:
        MongoDBConnector: Connected MongoDB connector instance
    """
    connector = MongoDBConnector()
    await connector.connect()
    try:
        yield connector
    finally:
        await connector.disconnect()


def get_db_settings() -> MongoDBSettings:
    """
    Lightweight dependency for MongoDB connection settings.

    Returns configuration (connection string, database name) without opening
    a connection. Used for operations that only need config, not database access.

    Usage:
        @router.post("/backup-database")
        async def backup_database(settings: MongoDBSettings = Depends(get_db_settings)):
            # Use settings.mongodb_connection_string, settings.database_name
            ...

    Returns:
        MongoDBSettings: MongoDB configuration loaded from credential files (~1ms)
    """
    return MongoDBSettings.create_from_credentials()
