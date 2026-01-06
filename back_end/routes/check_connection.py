# check_connection.py
"""
Health check endpoint for MongoDB connection status.

Returns connection status, database name, server info, and collection count.
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging
from db_connector.connection import MongoDBConnector
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/check-connection", response_model=Dict[str, Any])
async def check_connection(db: MongoDBConnector = Depends(get_db)) -> Dict[str, Any]:
    """
    Check MongoDB connection health and return status information.

    Returns:
        dict: Connection status including:
            - connected (bool): Whether connection is established
            - database (str): Database name
            - collections_count (int): Number of collections
            - server_info (dict): MongoDB server version and platform
            - ping_success (bool): Whether ping command succeeded

    Raises:
        HTTPException: 500 if connection check fails
    """
    try:
        health_info = await db.health_check()
        logger.info(f"Health check completed: connected={health_info.get('connected')}")
        return health_info

    except Exception as e:
        raise api_error("Connection check", e)