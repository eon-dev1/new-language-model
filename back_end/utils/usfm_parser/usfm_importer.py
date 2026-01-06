# usfm_importer.py
"""
MongoDB import functionality for USFM Bible data.

Imports parsed USFM verses into MongoDB collections with batch operations
and upsert support.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from .usfm_parser import parse_usfm_file, parse_usfm_directory, ParsedVerse, ParseResult

logger = logging.getLogger(__name__)

# Collection names (matching new_language.py)
BIBLE_TEXTS_COLLECTION = "bible_texts"
BIBLE_BOOKS_COLLECTION = "bible_books"


@dataclass
class ImportResult:
    """Result of MongoDB import operation."""
    verses_imported: int = 0
    verses_updated: int = 0
    books_processed: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.verses_imported + self.verses_updated

    @property
    def success(self) -> bool:
        return self.total_processed > 0


def _verse_to_document(
    verse: ParsedVerse,
    language_code: str,
    translation_type: str,
    language_name: str = None
) -> dict:
    """
    Convert a ParsedVerse to a MongoDB document.

    Args:
        verse: Parsed verse data
        language_code: Language code (e.g., "english", "kope")
        translation_type: "human" or "ai"
        language_name: Display name for the language (optional, defaults to language_code)

    Returns:
        Dictionary suitable for MongoDB insert/update
    """
    now = datetime.utcnow()

    # For English (base language), text goes to english_text
    # For other languages, it could go to translated_text
    is_english = language_code.lower() == "english"

    doc = {
        "language_code": language_code,
        "language_name": language_name if language_name else language_code,
        "book_code": verse.book_code,
        "chapter": verse.chapter,
        "verse": verse.verse,
        "translation_type": translation_type,
        "english_text": verse.clean_text if is_english else "",
        "translated_text": "" if is_english else verse.clean_text,
        "footnotes": verse.footnotes if verse.footnotes else [],
        "human_verified": False,
        "updated_at": now,
    }

    return doc


async def import_usfm_to_mongodb(
    filepath: Path | str,
    language_code: str = "english",
    language_name: str = None,
    translation_type: str = "human",
    batch_size: int = 500,
    connector = None
) -> ImportResult:
    """
    Import a single USFM file into MongoDB.

    Args:
        filepath: Path to USFM file
        language_code: Target language code (default: "english")
        language_name: Display name for the language (optional)
        translation_type: "human" or "ai" (default: "human")
        batch_size: Number of documents per batch operation
        connector: Optional MongoDBConnector instance (creates new if None)

    Returns:
        ImportResult with statistics
    """
    # Import here to avoid circular imports
    from db_connector.connection import MongoDBConnector

    filepath = Path(filepath)
    result = ImportResult()

    # Parse the USFM file
    parse_result = parse_usfm_file(filepath)
    if not parse_result.verses:
        result.errors.extend(parse_result.errors)
        if not parse_result.errors:
            result.errors.append(f"No verses parsed from {filepath}")
        return result

    result.books_processed = parse_result.books_parsed

    # Determine if we should manage the connection
    manage_connection = connector is None

    try:
        if manage_connection:
            connector = MongoDBConnector()
            await connector.connect()

        db = connector.get_database()
        collection = db[BIBLE_TEXTS_COLLECTION]

        logger.info(f"Importing {len(parse_result.verses)} verses to {BIBLE_TEXTS_COLLECTION}")

        # Process in batches
        for i in range(0, len(parse_result.verses), batch_size):
            batch = parse_result.verses[i:i + batch_size]
            operations = []

            for verse in batch:
                doc = _verse_to_document(verse, language_code, translation_type, language_name)

                # Use upsert to handle existing documents
                filter_doc = {
                    "language_code": language_code,
                    "book_code": verse.book_code,
                    "chapter": verse.chapter,
                    "verse": verse.verse,
                    "translation_type": translation_type
                }

                # Build update operation
                update_doc = {
                    "$set": doc,
                    "$setOnInsert": {"created_at": datetime.utcnow()}
                }

                operations.append({
                    "filter": filter_doc,
                    "update": update_doc,
                    "upsert": True
                })

            # Execute batch with bulk_write using UpdateOne
            from pymongo import UpdateOne
            bulk_operations = [
                UpdateOne(op["filter"], op["update"], upsert=op["upsert"])
                for op in operations
            ]

            bulk_result = await collection.bulk_write(bulk_operations, ordered=False)

            result.verses_imported += bulk_result.upserted_count
            result.verses_updated += bulk_result.modified_count

            logger.debug(f"Batch {i//batch_size + 1}: {bulk_result.upserted_count} inserted, {bulk_result.modified_count} updated")

        logger.info(f"Import complete: {result.verses_imported} inserted, {result.verses_updated} updated")

    except Exception as e:
        error_msg = f"MongoDB import error: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)
    finally:
        if manage_connection and connector:
            await connector.disconnect()

    return result


async def import_usfm_directory_to_mongodb(
    dirpath: Path | str,
    language_code: str = "english",
    language_name: str = None,
    translation_type: str = "human",
    batch_size: int = 500,
    pattern: str = None
) -> ImportResult:
    """
    Import all USFM files from a directory into MongoDB.

    Args:
        dirpath: Path to directory containing USFM files
        language_code: Target language code (default: "english")
        language_name: Display name for the language (optional)
        translation_type: "human" or "ai" (default: "human")
        batch_size: Number of documents per batch operation
        pattern: Glob pattern for USFM files. If None, auto-detects (*.usfm, *.SFM, etc.)

    Returns:
        ImportResult with combined statistics
    """
    # Import here to avoid circular imports
    from db_connector.connection import MongoDBConnector

    dirpath = Path(dirpath)
    result = ImportResult()

    if not dirpath.exists():
        result.errors.append(f"Directory not found: {dirpath}")
        return result

    # Auto-detect file extension if pattern not specified
    if pattern is None:
        for try_pattern in ["*.usfm", "*.SFM", "*.sfm", "*.USFM"]:
            usfm_files = list(dirpath.glob(try_pattern))
            if usfm_files:
                pattern = try_pattern
                logger.info(f"Auto-detected USFM pattern: {pattern}")
                break
        else:
            pattern = "*.usfm"  # Default fallback

    usfm_files = sorted(dirpath.glob(pattern))
    if not usfm_files:
        result.errors.append(f"No USFM files found in {dirpath}")
        return result

    logger.info(f"Found {len(usfm_files)} USFM files to import")

    # Use single connection for all files
    connector = MongoDBConnector()

    try:
        await connector.connect()

        for usfm_file in usfm_files:
            logger.info(f"Processing: {usfm_file.name}")

            file_result = await import_usfm_to_mongodb(
                usfm_file,
                language_code=language_code,
                language_name=language_name,
                translation_type=translation_type,
                batch_size=batch_size,
                connector=connector
            )

            result.verses_imported += file_result.verses_imported
            result.verses_updated += file_result.verses_updated
            result.books_processed += file_result.books_processed
            result.errors.extend(file_result.errors)

        logger.info(f"Directory import complete: {result.books_processed} books, "
                   f"{result.verses_imported} inserted, {result.verses_updated} updated")

    except Exception as e:
        error_msg = f"Directory import error: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)
    finally:
        await connector.disconnect()

    return result


async def update_bible_books_collection(
    language_code: str = "english",
    translation_type: str = "human",
    connector = None
) -> int:
    """
    Update bible_books collection with verse text from bible_texts.

    This syncs the embedded verses in bible_books with the individual
    verse documents in bible_texts. Usually run after import_usfm_*.

    Args:
        language_code: Language to update
        translation_type: Translation type to update
        connector: Optional MongoDBConnector instance

    Returns:
        Number of books updated
    """
    # Import here to avoid circular imports
    from db_connector.connection import MongoDBConnector

    manage_connection = connector is None
    books_updated = 0

    try:
        if manage_connection:
            connector = MongoDBConnector()
            await connector.connect()

        db = connector.get_database()
        texts_collection = db[BIBLE_TEXTS_COLLECTION]
        books_collection = db[BIBLE_BOOKS_COLLECTION]

        # Get all unique book codes for this language/type
        pipeline = [
            {"$match": {
                "language_code": language_code,
                "translation_type": translation_type
            }},
            {"$group": {"_id": "$book_code"}}
        ]

        book_codes = [doc["_id"] async for doc in texts_collection.aggregate(pipeline)]

        logger.info(f"Updating {len(book_codes)} books in bible_books collection")

        for book_code in book_codes:
            # Get all verses for this book
            verses_cursor = texts_collection.find({
                "language_code": language_code,
                "book_code": book_code,
                "translation_type": translation_type
            }).sort([("chapter", 1), ("verse", 1)])

            # Group by chapter
            chapters_data = {}
            async for verse_doc in verses_cursor:
                chapter_num = verse_doc["chapter"]
                if chapter_num not in chapters_data:
                    chapters_data[chapter_num] = []

                chapters_data[chapter_num].append({
                    "verse_number": verse_doc["verse"],
                    "english_text": verse_doc.get("english_text", ""),
                    "translated_text": verse_doc.get("translated_text", ""),
                    "comments": ""
                })

            # Update bible_books document
            if chapters_data:
                # Build chapters array update
                update_chapters = []
                for chapter_num in sorted(chapters_data.keys()):
                    verses = sorted(chapters_data[chapter_num], key=lambda v: v["verse_number"])
                    update_chapters.append({
                        "chapter_number": chapter_num,
                        "verse_count": len(verses),
                        "verses": verses
                    })

                await books_collection.update_one(
                    {
                        "language_code": language_code,
                        "book_code": book_code,
                        "translation_type": translation_type
                    },
                    {
                        "$set": {
                            "chapters": update_chapters,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                books_updated += 1

        logger.info(f"Updated {books_updated} book documents")

    except Exception as e:
        logger.error(f"Error updating bible_books: {e}")
    finally:
        if manage_connection and connector:
            await connector.disconnect()

    return books_updated


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python usfm_importer.py <usfm_file_or_directory> [language_code] [translation_type]")
            print("\nExamples:")
            print("  python usfm_importer.py data/bibles/engnet_usfm/")
            print("  python usfm_importer.py 02-GENengnet.usfm english human")
            sys.exit(1)

        path = Path(sys.argv[1])
        language_code = sys.argv[2] if len(sys.argv) > 2 else "english"
        translation_type = sys.argv[3] if len(sys.argv) > 3 else "human"

        print(f"Importing USFM data to MongoDB")
        print(f"  Path: {path}")
        print(f"  Language: {language_code}")
        print(f"  Translation Type: {translation_type}")
        print("-" * 50)

        if path.is_file():
            result = await import_usfm_to_mongodb(
                path,
                language_code=language_code,
                translation_type=translation_type
            )
        elif path.is_dir():
            result = await import_usfm_directory_to_mongodb(
                path,
                language_code=language_code,
                translation_type=translation_type
            )
        else:
            print(f"Path not found: {path}")
            sys.exit(1)

        print(f"\nImport Results:")
        print(f"  Books processed: {result.books_processed}")
        print(f"  Verses inserted: {result.verses_imported}")
        print(f"  Verses updated: {result.verses_updated}")
        print(f"  Total processed: {result.total_processed}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:10]:
                print(f"  - {error}")

        return result.success

    success = asyncio.run(main())
    sys.exit(0 if success else 1)