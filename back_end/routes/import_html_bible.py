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
from constants import Collection
from .dependencies import get_db, api_error

logger = logging.getLogger(__name__)
router = APIRouter()


class ImportHtmlBibleRequest(BaseModel):
    language_code: str
    language_name: str
    html_directory: str
    translation_type: str = "human"


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
    dirpath = Path(request.html_directory)

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
            translation_type=request.translation_type
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
        # This makes the imported project visible in "Continue Journey"
        database = db.get_database()
        languages_collection = database[Collection.LANGUAGES]
        existing_language = await languages_collection.find_one({"language_code": request.language_code})

        total_verses = result.verses_imported + result.verses_updated
        translation_key = request.translation_type  # "human" or "ai"

        if not existing_language:
            language_doc = {
                "language_name": request.language_name,
                "language_code": request.language_code,
                "is_base_language": False,
                "created_at": datetime.utcnow(),
                "status": "active",
                "bible_books_count": result.books_processed,
                "total_verses": total_verses,
                "translation_levels": {
                    "human": {
                        "books_started": result.books_processed if translation_key == "human" else 0,
                        "books_completed": 0,
                        "verses_translated": total_verses if translation_key == "human" else 0,
                        "last_updated": datetime.utcnow() if translation_key == "human" else None
                    },
                    "ai": {
                        "books_started": result.books_processed if translation_key == "ai" else 0,
                        "books_completed": 0,
                        "verses_translated": total_verses if translation_key == "ai" else 0,
                        "last_updated": datetime.utcnow() if translation_key == "ai" else None,
                        "model_version": "nlm-v1.0"
                    }
                },
                "metadata": {
                    "creator": "import_html_endpoint",
                    "version": "1.0",
                    "description": f"Imported from HTML files",
                    "dual_level_support": True
                }
            }
            await languages_collection.insert_one(language_doc)
            logger.info(f"Created language document for {request.language_name}")
        else:
            # Update existing language with new import stats
            await languages_collection.update_one(
                {"language_code": request.language_code},
                {"$set": {
                    "updated_at": datetime.utcnow(),
                    f"translation_levels.{translation_key}.verses_translated": total_verses,
                    f"translation_levels.{translation_key}.books_started": result.books_processed,
                    f"translation_levels.{translation_key}.last_updated": datetime.utcnow()
                }}
            )
            logger.info(f"Updated language document for {request.language_name}")

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
