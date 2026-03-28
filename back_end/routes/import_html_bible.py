# import_html_bible.py
"""
HTML Bible import endpoint.

Imports HTML-format Bible files from a directory into MongoDB.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import logging

from db_connector.connection import MongoDBConnector
from utils.html_parser.html_importer import import_html_directory_to_mongodb
from utils.usfm_parser.usfm_importer import sync_bible_books_from_texts
from utils.word_index.builder import build_word_index
from constants import Collection
from .dependencies import get_db, api_error

logger = logging.getLogger(__name__)
router = APIRouter()


class ImportHtmlBibleRequest(BaseModel):
    language_code: str
    language_name: str
    html_directory: str
    human_verified: bool = False


class ImportHtmlBibleResponse(BaseModel):
    success: bool
    language_code: str
    message: str
    verses_imported: int
    verses_updated: int
    chapters_processed: int
    is_reimport: bool


@router.post("/import-html-bible", response_model=ImportHtmlBibleResponse)
async def import_html_bible(
    request: ImportHtmlBibleRequest,
    db: MongoDBConnector = Depends(get_db)
):
    """
    Import HTML Bible files from a directory into MongoDB.

    Expects HTML files with naming pattern: {BookCode}{ChapterNumber}.htm
    Example: MAT01.htm, JHN03.htm

    Skips chapter 00 files (introductions).
    Handles both fresh imports and re-imports (upsert behavior).
    """
    dirpath = Path(request.html_directory).resolve()

    if not dirpath.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Directory not found: {request.html_directory}"
        )

    if not dirpath.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {request.html_directory}"
        )

    logger.info(f"Starting HTML Bible import for {request.language_name} from {dirpath}")

    try:
        result = await import_html_directory_to_mongodb(
            dirpath=dirpath,
            language_code=request.language_code,
            language_name=request.language_name,
            human_verified=request.human_verified,
        )

        if result.errors:
            logger.warning(f"Import completed with errors: {result.errors}")

        # Determine if this was a re-import
        is_reimport = result.verses_updated > 0 and result.verses_imported == 0

        # Generate human-readable message
        if is_reimport:
            message = f"Updated {result.verses_updated} existing verses in {result.books_processed} chapters"
        elif result.verses_updated > 0:
            message = f"Imported {result.verses_imported} new verses, updated {result.verses_updated} existing verses across {result.books_processed} chapters"
        else:
            message = f"Imported {result.verses_imported} verses from {result.books_processed} chapters"

        # Ensure language document exists in languages collection
        database = db.get_database()
        languages_collection = database[Collection.LANGUAGES]
        bible_texts = database[Collection.BIBLE_TEXTS]
        existing_language = await languages_collection.find_one({"language_code": request.language_code})

        total_verses = result.verses_imported + result.verses_updated

        # Count human-verified verses after import
        verses_verified = await bible_texts.count_documents({
            "language_code": request.language_code,
            "human_verified": True
        })

        if not existing_language:
            language_doc = {
                "language_name": request.language_name,
                "language_code": request.language_code,
                "is_base_language": False,
                "created_at": datetime.utcnow(),
                "status": "active",
                "bible_books_count": result.books_processed,
                "total_verses": total_verses,
                "translation_stats": {
                    "books_started": result.books_processed,
                    "books_completed": 0,
                    "verses_translated": total_verses,
                    "verses_verified": verses_verified,
                    "last_updated": datetime.utcnow()
                },
                "metadata": {
                    "creator": "import_html_endpoint",
                    "version": "1.0",
                    "description": "Imported from HTML files",
                }
            }
            await languages_collection.insert_one(language_doc)
            logger.info(f"Created language document for {request.language_name}")
        else:
            await languages_collection.update_one(
                {"language_code": request.language_code},
                {"$set": {
                    "updated_at": datetime.utcnow(),
                    "translation_stats.verses_translated": total_verses,
                    "translation_stats.books_started": result.books_processed,
                    "translation_stats.verses_verified": verses_verified,
                    "translation_stats.last_updated": datetime.utcnow()
                }}
            )
            logger.info(f"Updated language document for {request.language_name}")

        # Rebuild word index after import
        try:
            idx = await build_word_index(db, request.language_code)
            logger.info(f"Word index rebuilt: {idx['words_indexed']} words in {idx['duration_ms']}ms")
        except Exception as idx_err:
            logger.warning(f"Word index rebuild failed (non-fatal): {idx_err}")

        # Sync bible_books metadata from imported bible_texts
        try:
            synced = await sync_bible_books_from_texts(
                request.language_code, db
            )
            logger.info(f"bible_books sync: {synced} books")
        except Exception as sync_err:
            logger.warning(f"bible_books sync failed (non-fatal): {sync_err}")

        return ImportHtmlBibleResponse(
            success=result.success,
            language_code=request.language_code,
            message=message,
            verses_imported=result.verses_imported,
            verses_updated=result.verses_updated,
            chapters_processed=result.books_processed,
            is_reimport=is_reimport
        )

    except Exception as e:
        raise api_error(f"Import HTML Bible for {request.language_name}", e)
