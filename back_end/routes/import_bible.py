# import_bible.py
"""
USFM Bible import endpoint.

Imports USFM Bible files from a directory into MongoDB.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import logging

from db_connector.connection import MongoDBConnector
from utils.usfm_parser.usfm_importer import (
    import_usfm_directory_to_mongodb,
    sync_bible_books_from_texts
)
from utils.word_index.builder import build_word_index
from utils.phrase_index.builder import build_phrase_index
from constants import Collection
from .dependencies import get_db, api_error

logger = logging.getLogger(__name__)
router = APIRouter()


class ImportBibleRequest(BaseModel):
    language_code: str
    language_name: str
    usfm_directory: str
    human_verified: bool = False


class ImportBibleResponse(BaseModel):
    success: bool
    language_code: str
    message: str
    verses_imported: int
    verses_updated: int
    books_processed: int
    is_reimport: bool


@router.post("/import-bible", response_model=ImportBibleResponse)
async def import_bible(
    request: ImportBibleRequest,
    db: MongoDBConnector = Depends(get_db)
):
    """
    Import USFM Bible files from a directory into MongoDB.

    Auto-detects USFM file extensions (*.usfm, *.SFM, etc.)
    Handles both fresh imports and re-imports (upsert behavior).
    """
    dirpath = Path(request.usfm_directory).resolve()

    if not dirpath.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Directory not found: {request.usfm_directory}"
        )

    if not dirpath.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {request.usfm_directory}"
        )

    logger.info(f"Starting Bible import for {request.language_name} from {dirpath}")

    try:
        result = await import_usfm_directory_to_mongodb(
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
            message = f"Updated {result.verses_updated} existing verses in {result.books_processed} books"
        elif result.verses_updated > 0:
            message = f"Imported {result.verses_imported} new verses, updated {result.verses_updated} existing verses across {result.books_processed} books"
        else:
            message = f"Imported {result.verses_imported} verses from {result.books_processed} books"

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
                "created_at": datetime.now(timezone.utc),
                "status": "active",
                "bible_books_count": result.books_processed,
                "total_verses": total_verses,
                "translation_stats": {
                    "books_started": result.books_processed,
                    "books_completed": 0,
                    "verses_translated": total_verses,
                    "verses_verified": verses_verified,
                    "last_updated": datetime.now(timezone.utc)
                },
                "metadata": {
                    "creator": "import_usfm_endpoint",
                    "version": "1.0",
                    "description": "Imported from USFM files",
                }
            }
            await languages_collection.insert_one(language_doc)
            logger.info(f"Created language document for {request.language_name}")
        else:
            await languages_collection.update_one(
                {"language_code": request.language_code},
                {"$set": {
                    "updated_at": datetime.now(timezone.utc),
                    "translation_stats.verses_translated": total_verses,
                    "translation_stats.books_started": result.books_processed,
                    "translation_stats.verses_verified": verses_verified,
                    "translation_stats.last_updated": datetime.now(timezone.utc)
                }}
            )
            logger.info(f"Updated language document for {request.language_name}")

        # Rebuild word index after import
        try:
            idx = await build_word_index(db, request.language_code)
            logger.info(f"Word index rebuilt: {idx['words_indexed']} words in {idx['duration_ms']}ms")
        except Exception as idx_err:
            logger.warning(f"Word index rebuild failed (non-fatal): {idx_err}")

        # Rebuild phrase index for the imported target language.
        # Verified-only filter applies inside the builder; if the import set
        # human_verified=False everywhere, this emits an empty index — which
        # is the correct behavior.
        try:
            pidx = await build_phrase_index(db, request.language_code)
            logger.info(
                f"Phrase index rebuilt: {pidx['phrases_emitted']} phrases in {pidx['duration_ms']}ms"
            )
        except Exception as pidx_err:
            logger.warning(f"Phrase index rebuild failed (non-fatal): {pidx_err}")

        # Sync bible_books metadata from imported bible_texts
        try:
            synced = await sync_bible_books_from_texts(
                request.language_code, db
            )
            logger.info(f"bible_books sync: {synced} books")
        except Exception as sync_err:
            logger.warning(f"bible_books sync failed (non-fatal): {sync_err}")

        return ImportBibleResponse(
            success=result.success,
            language_code=request.language_code,
            message=message,
            verses_imported=result.verses_imported,
            verses_updated=result.verses_updated,
            books_processed=result.books_processed,
            is_reimport=is_reimport
        )

    except Exception as e:
        raise api_error(f"Import Bible for {request.language_name}", e)
