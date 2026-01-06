# routes/dependencies.py
"""
FastAPI dependency injection and utilities for routes.

Provides request-scoped MongoDB connections and error handling utilities.
"""

import logging
from typing import AsyncGenerator
from fastapi import HTTPException
from db_connector.connection import MongoDBConnector

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
    logger.error(f"{operation} failed: {e}")
    return HTTPException(status_code=status, detail=f"{operation} failed: {str(e)}")


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
