# html_importer.py
"""
MongoDB import functionality for HTML Bible data.

Imports parsed HTML verses into MongoDB collections with batch operations
and upsert support. Reuses core import logic from USFM importer.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .html_parser import parse_html_file, parse_html_directory

# Reuse from USFM importer
from utils.usfm_parser.usfm_importer import (
    _verse_to_document,
    ImportResult,
    BIBLE_TEXTS_COLLECTION,
)
from utils.usfm_parser.usfm_parser import ParsedVerse

logger = logging.getLogger(__name__)


async def import_html_to_mongodb(
    filepath: Path | str,
    language_code: str = "english",
    language_name: str = None,
    translation_type: str = "human",
    batch_size: int = 500,
    connector=None
) -> ImportResult:
    """
    Import a single HTML chapter file into MongoDB.

    Args:
        filepath: Path to HTML file
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

    # Parse the HTML file
    parse_result = parse_html_file(filepath)
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


async def import_html_directory_to_mongodb(
    dirpath: Path | str,
    language_code: str = "english",
    language_name: str = None,
    translation_type: str = "human",
    batch_size: int = 500,
    pattern: str = "*.htm"
) -> ImportResult:
    """
    Import all HTML Bible files from a directory into MongoDB.

    Args:
        dirpath: Path to directory containing HTML files
        language_code: Target language code (default: "english")
        language_name: Display name for the language (optional)
        translation_type: "human" or "ai" (default: "human")
        batch_size: Number of documents per batch operation
        pattern: Glob pattern for HTML files (default: "*.htm")

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

    # Get valid HTML files (filtering handled by parse_html_directory)
    html_files = sorted(dirpath.glob(pattern))

    # Filter to valid chapter files
    from .html_parser import extract_book_chapter_from_filename
    valid_files = []
    for html_file in html_files:
        extracted = extract_book_chapter_from_filename(html_file.name)
        if extracted:
            usfm_code, chapter = extracted
            if chapter > 0:  # Skip chapter 00 (introductions)
                valid_files.append(html_file)

    if not valid_files:
        result.errors.append(f"No valid HTML chapter files found in {dirpath}")
        return result

    logger.info(f"Found {len(valid_files)} HTML chapter files to import")

    # Use single connection for all files
    connector = MongoDBConnector()

    try:
        await connector.connect()

        for html_file in valid_files:
            logger.info(f"Processing: {html_file.name}")

            file_result = await import_html_to_mongodb(
                html_file,
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

        logger.info(f"Directory import complete: {result.books_processed} chapters, "
                   f"{result.verses_imported} inserted, {result.verses_updated} updated")

    except Exception as e:
        error_msg = f"Directory import error: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)
    finally:
        await connector.disconnect()

    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python html_importer.py <html_file_or_directory> [language_code] [translation_type]")
            print("\nExamples:")
            print("  python html_importer.py data/bibles/bgt_html/")
            print("  python html_importer.py data/bibles/bgt_html/MAT01.htm bughotu human")
            sys.exit(1)

        path = Path(sys.argv[1])
        language_code = sys.argv[2] if len(sys.argv) > 2 else "english"
        translation_type = sys.argv[3] if len(sys.argv) > 3 else "human"

        print(f"Importing HTML Bible data to MongoDB")
        print(f"  Path: {path}")
        print(f"  Language: {language_code}")
        print(f"  Translation Type: {translation_type}")
        print("-" * 50)

        if path.is_file():
            result = await import_html_to_mongodb(
                path,
                language_code=language_code,
                translation_type=translation_type
            )
        elif path.is_dir():
            result = await import_html_directory_to_mongodb(
                path,
                language_code=language_code,
                translation_type=translation_type
            )
        else:
            print(f"Path not found: {path}")
            sys.exit(1)

        print(f"\nImport Results:")
        print(f"  Chapters processed: {result.books_processed}")
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
