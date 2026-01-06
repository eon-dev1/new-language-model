# create_base_language_bible_dataset.py

"""
Create base language Bible dataset in MongoDB.

This module creates the foundational Bible structure without any translation text,
serving as the base reference for all language translations.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# Add parent directories to path for imports
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent  # Go up to nlm_fastapi_endpoint
sys.path.insert(0, str(project_root))

from utils.bible_generator.bible_collection_manager import BibleCollectionManager
from utils.bible_generator.chapter_verse_numbers import BIBLE_CHAPTER_VERSES, get_chapters_for_book
from db_connector.connection import MongoDBConnector, get_mongodb_connector

logger = logging.getLogger(__name__)

class BaseLanguageBibleManager(BibleCollectionManager):
    """
    Manager for creating and managing base language Bible collections.
    
    The base language Bible contains only the structural information:
    - Book names
    - Chapter numbers
    - Verse numbers
    No actual text content, dictionary, or grammar is included.
    """

    async def create_collection(self, collection_name: Optional[str] = None) -> str:
        """
        Create a new base language Bible collection.
        
        Args:
            collection_name: Optional custom collection name
            
        Returns:
            str: The name of the created collection
        """
        if not collection_name:
            collection_name = self.format_collection_name("base", "structure", "bible")

        # Check if collection already exists
        if await self.collection_exists(collection_name):
            logger.info(f"Collection {collection_name} already exists")
            return collection_name
      
        # Get the collection
        collection = await self.get_collection(collection_name)

        # Create indexes
        await self.create_bible_indexes(collection)

        logger.info(f"Created base language Bible collection: {collection_name}")
        return collection_name
    
    async def populate_collection(self, collection_name: str, testament: Optional[str] = None) -> int:
        """
        Populate the base language Bible collection with structure from chapter_verse_numbers.py.
        
        Args:
            collection_name: Name of the collection to populate
            testament: Optional - "old", "new", or None for both
            
        Returns:
            int: Number of documents inserted
        """
        collection = await self.get_collection(collection_name)
        
        # Define Old Testament and New Testament books
        old_testament_books = [
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
            "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
            "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
            "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
            "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
            "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
            "Amos", "Obadiah", "Jonah", "Micah", "Nahum",
            "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi"
        ]
        
        new_testament_books = [
            "Matthew", "Mark", "Luke", "John", "Acts",
            "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
            "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
            "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus",
            "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
            "1 John", "2 John", "3 John", "Jude", "Revelation"
        ]

        # Determine which books to process based on testament parameter
        books_to_process = []
        if testament == "old":
            books_to_process = old_testament_books
        elif testament == "new":
            books_to_process = new_testament_books
        else:
            # Process all books
            books_to_process = old_testament_books + new_testament_books

        documents = []
        book_order = 0

        # Track overall book order (1-66)
        all_books = old_testament_books + new_testament_books

        for book_name in books_to_process:
            # Get chapter and verse data from imported module
            chapters_verses = get_chapters_for_book(book_name)

            if not chapters_verses:
                logger.warning(f"No chapter/verse data found for book: {book_name}")
                continue
        
            # Calculate book order (1-based index in full Bible)
            book_order = all_books.index(book_name) + 1

            # Determine testament
            testament_name = "Old" if book_name in old_testament_books else "New"

            # Process each chapter and verse
            for chapter_num, verse_count in chapters_verses:
                for verse_num in range(1, verse_count + 1):
                    # Create document without text content
                    doc = self.create_bible_document(
                        book=book_name,
                        chapter=chapter_num,
                        verse=verse_num,
                        text="",  # No text for base language
                        translation="BASE",
                        language_code="base",
                        book_order=book_order,
                        testament=testament_name,
                        is_base_structure=True
                    )
                    documents.append(doc)

        # Bulk insert documents
        if documents:
            result = await collection.insert_many(documents)
            inserted_count = len(result.inserted_ids)
            logger.info(f"Inserted {inserted_count} base structure documents into {collection_name}")
            return inserted_count
        
        return 0
    
    async def get_structure_summary(self, collection_name: str) -> Dict[str, Any]:
        """
        Get a summary of the base language Bible structure.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dict containing structure summary
        """
        stats = await self.get_collection_stats(collection_name)

        # Count total expected books from BIBLE_CHAPTER_VERSES
        total_books = len(BIBLE_CHAPTER_VERSES)

        # Add specific base language information
        stats.update({
            "type": "base_language_structure",
            "has_text": False,
            "has_dictionary": False,
            "has_grammar": False,
            "purpose": "Reference structure for all translations",
            "total_books_expected": total_books,
            "old_testament_books": 39,
            "new_testament_books": 27
        })
        
        return stats

async def create_base_language_bible(
    db_connector: Optional[MongoDBConnector] = None,
    collection_name: Optional[str] = None,
    testament: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main function to create and populate a base language Bible collection.
    
    Args:
        db_connector: Optional MongoDB connector instance
        collection_name: Optional custom collection name
        testament: Optional - "old", "new", or None for both
        
    Returns:
        Dict with creation results
    """
    # Get or create connector
    if not db_connector:
        db_connector = await get_mongodb_connector()

    # Create manager
    manager = BaseLanguageBibleManager(db_connector)

    try:
        # Create collection
        collection_name = await manager.create_collection(collection_name)

        # Populate with base structure
        doc_count = await manager.populate_collection(collection_name, testament)

        # Get summary
        summary = await manager.get_structure_summary(collection_name)

        return {
            "success": True,
            "collection_name": collection_name,
            "documents_created": doc_count,
            "summary": summary
        }
    
    except Exception as e:
        logger.error(f"Error creating base language Bible: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        # Don't close the global connector
        pass


async def main():
    """
    Example usage of the base language Bible creator.
    """
    logging.basicConfig(level=logging.INFO)
    
    # Create base language Bible
    result = await create_base_language_bible(
        collection_name="base_structure_bible",
        testament=None  # Create both testaments
    )
    
    if result["success"]:
        print(f"✅ Successfully created base language Bible")
        print(f"   Collection: {result['collection_name']}")
        print(f"   Documents: {result['documents_created']}")
        print(f"   Summary: {result['summary']}")
    else:
        print(f"❌ Failed to create base language Bible: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())