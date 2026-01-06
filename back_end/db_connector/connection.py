# db_connector/core/connection.py
# MongoDB Atlas connection manager using Motor

import asyncio
from typing import Optional, Dict, Any
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from db_connector.settings import MongoDBSettings

logger = logging.getLogger(__name__)

class MongoDBConnector:
    """MongoDB connection manager using Motor"""

    def __init__(self, settings: Optional[MongoDBSettings] = None):
        self.settings = settings or MongoDBSettings.create_from_credentials()
        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None
        self._is_connected = False

        logger.info(f"Initialized MongoDB connector: {self.settings}")

    async def connect(self) -> None:
        """Establish connection to MongoDB Atlas"""
        if self._is_connected and self._client:
            logger.info("MongoDB connection already established")
            return
        
        try:
            # Create Motor client with connection options
            connection_options = self.settings.get_connection_options()
            
            logger.info(f"Connecting to MongoDB Atlas database: {self.settings.database_name}")
            
            self._client = AsyncIOMotorClient(
                self.settings.mongodb_connection_string,
                **connection_options
            )

            # Get database reference
            self._database = self._client[self.settings.database_name]

            # Test the connection
            await self._client.admin.command('ping')
            self._is_connected = True
            
            logger.info(f"✅ MongoDB connection established successfully to database: {self.settings.database_name}")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self._is_connected = False
            raise
        except Exception as e:
            logger.error(f"Unexpected error during MongoDB connection: {e}")
            self._is_connected = False
            raise

    async def disconnect(self) -> None:
        """Close MongoDB connection"""
        if self._client:
            try:
                self._client.close()
                self._is_connected = False
                logger.info("🔌 MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")
        
        self._client = None
        self._database = None

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check on MongoDB connection"""
        health_info = {
            "connected": False,
            "database": self.settings.database_name,
            "collections_count": 0,
            "ping_success": False,
            "server_info": None,
        }

        try:
            if not self._is_connected or not self._client:
                await self.connect()

            # Ensure client and database are not None after connection
            if self._client is not None and self._database is not None:
                # Test ping
                ping_result = await self._client.admin.command('ping')
                health_info["ping_success"] = ping_result.get("ok") == 1
                
                # Get server information
                server_info = await self._client.server_info()
                health_info["server_info"] = {
                    "version": server_info.get("version"),
                    "platform": server_info.get("platform", "unknown")
                }
                
                # Count collections
                collection_names = await self._database.list_collection_names()
                health_info["collections_count"] = len(collection_names)
                health_info["collections"] = collection_names[:10]  # First 10 for brevity
            else:
                health_info["error"] = "Failed to establish connection"
            
            health_info["connected"] = True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_info["error"] = str(e)
        
        return health_info
    
    def get_client(self) -> AsyncIOMotorClient:
        """Get the Motor client instance"""
        if not self._client:
            raise RuntimeError("MongoDB client not initialized. Call connect() first.")
        return self._client
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Get the Motor database instance"""
        if self._database is None:
            raise RuntimeError("MongoDB database not initialized. Call connect() first.")
        return self._database
    
    def get_collection(self, collection_name: str):
        """Get a specific collection from the database"""
        database = self.get_database()
        return database[collection_name]
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is established"""
        return self._is_connected and self._client is not None
    
    async def ensure_connected(self) -> None:
        """Ensure connection is established, connect if not"""
        if not self.is_connected:
            await self.connect()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


# Global connector instance
_global_connector: Optional[MongoDBConnector] = None

async def get_mongodb_connector() -> MongoDBConnector:
    """Get global MongoDB connector instance"""
    global _global_connector
    
    if _global_connector is None:
        _global_connector = MongoDBConnector()
        await _global_connector.connect()
    
    return _global_connector

async def close_mongodb_connector() -> None:
    """Close global MongoDB connector"""
    global _global_connector
    
    if _global_connector:
        await _global_connector.disconnect()
        _global_connector = None