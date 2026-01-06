# bible_collection_manager

"""
Abstract base class for Bible collection management in MongoDB.

This module provides the foundational BibleCollectionManager class that defines
the common interface and shared functionality for all Bible-related repository classes.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING
from bson import ObjectId

from db_connector.connection import MongoDBConnector


class BibleCollectionManager(ABC):
    """
    Abstract base class for managing Bible collections in MongoDB.
    
    Provides common functionality for Bible data operations including:
    - Database connection management
    - Collection access and creation
    - Document schema validation
    - Index management
    - Common query patterns
    """

    def __init__(self, db_connector: MongoDBConnector):
        """
        Initialize the Bible collection manager.
        
        Args:
            db_connector (MongoDBConnector): Database connection instance
        """
        self.db_connector = db_connector
        self._database: Optional[AsyncIOMotorDatabase] = None

    async def get_database(self) -> AsyncIOMotorDatabase:
        """
        Get the database instance, ensuring connection is established.
        
        Returns:
            AsyncIOMotorDatabase: The database instance
        """
        if self._database is None:
            if not self.db_connector.is_connected:
                await self.db_connector.connect()
            self._database = self.db_connector.get_database()
        return self._database

    async def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """
        Get a collection by name.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            AsyncIOMotorCollection: The collection instance
        """
        database = await self.get_database()
        return database[collection_name]
    
    def create_bible_document(
        self, 
        book: str, 
        chapter: int, 
        verse: int, 
        text: str = "",
        translation: str = "",
        language_code: str = "",
        **metadata: Any
    ) -> Dict[str, Any]:
        """
        Create a standardized Bible document structure.
        
        Args:
            book (str): Book name
            chapter (int): Chapter number
            verse (int): Verse number
            text (str): Verse text (empty for base language)
            translation (str): Translation identifier
            language_code (str): Language code (e.g., 'en', 'es')
            **metadata: Additional metadata fields
            
        Returns:
            Dict[str, Any]: Formatted document ready for insertion
        """
        now = datetime.utcnow()
        
        document = {
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "text": text,
            "translation": translation,
            "language_code": language_code,
            "created_at": now,
            "updated_at": now,
            **metadata
        }
        
        return document

    async def create_bible_indexes(self, collection: AsyncIOMotorCollection) -> None:
        """
        Create standard indexes for Bible collections.
        
        Args:
            collection (AsyncIOMotorCollection): Collection to create indexes on
        """
        indexes = [
            # Compound index for efficient verse lookups
            IndexModel([
                ("book", ASCENDING),
                ("chapter", ASCENDING), 
                ("verse", ASCENDING)
            ], name="book_chapter_verse_idx"),

            # Translation index for filtering by translation
            IndexModel([("translation", ASCENDING)], name="translation_idx"),

            # Language code index for filtering by language
            IndexModel([("language_code", ASCENDING)], name="language_code_idx"),

            # Book index for book-level queries
            IndexModel([("book", ASCENDING)], name="book_idx"),
            
            # Text index for search capabilities (only if text exists)
            IndexModel([("text", "text")], name="text_search_idx", sparse=True)
        ]

        try:
            await collection.create_indexes(indexes)
        except Exception as e:
            # Index creation might fail if they already exist, which is fine
            pass
    
    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics about a Bible collection.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            Dict[str, Any]: Collection statistics
        """
        collection = await self.get_collection(collection_name)

        total_docs = await collection.count_documents({})
        total_books = await collection.distinct("book")
        translations = await collection.distinct("translation")
        languages = await collection.distinct("language_code")

        # Sample aggregation to get chapter/verse counts
        pipeline = [
            {
                "$group": {
                    "_id": {"book": "$book", "chapter": "$chapter"},
                    "verse_count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": "$_id.book",
                    "chapter_count": {"$sum": 1},
                    "total_verses": {"$sum": "$verse_count"}
                }
            }
        ]
        
        book_stats = []
        async for doc in collection.aggregate(pipeline):
            book_stats.append(doc)
        
        return {
            "collection_name": collection_name,
            "total_documents": total_docs,
            "total_books": len(total_books),
            "books": sorted(total_books),
            "translations": sorted(translations),
            "languages": sorted(languages),
            "book_statistics": book_stats
        }

    @abstractmethod
    async def create_collection(self, **kwargs) -> str:
        """
        Create a new Bible collection.
        
        This method must be implemented by subclasses to define
        the specific collection creation logic.
        
        Returns:
            str: The name of the created collection
        """
        pass
    
    @abstractmethod
    async def populate_collection(self, collection_name: str, **kwargs) -> int:
        """
        Populate a Bible collection with data.
        
        This method must be implemented by subclasses to define
        the specific data population logic.
        
        Args:
            collection_name (str): Name of the collection to populate
            
        Returns:
            int: Number of documents inserted
        """
        pass
    
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a Bible collection.
        
        Args:
            collection_name (str): Name of the collection to delete
            
        Returns:
            bool: True if collection was deleted successfully
        """
        try:
            database = await self.get_database()
            await database.drop_collection(collection_name)
            return True
        except Exception as e:
            return False
    
    async def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            bool: True if collection exists
        """
        database = await self.get_database()
        collection_names = await database.list_collection_names()
        return collection_name in collection_names
    
    def format_collection_name(
        self, 
        language_code: str, 
        translation: str, 
        suffix: str = "bible"
    ) -> str:
        """
        Create a standardized collection name.
        
        Args:
            language_code (str): Language code (e.g., 'en')
            translation (str): Translation identifier (e.g., 'NET')
            suffix (str): Collection suffix (default: 'bible')
            
        Returns:
            str: Formatted collection name
        """
        return f"{language_code.lower()}_{translation.lower()}_{suffix}"
    
    async def close(self) -> None:
        """
        Close the database connection.
        """
        if self.db_connector.is_connected:
            await self.db_connector.disconnect()
        self._database = None