# load_base_language.py
"""
Endpoint to ensure the base language (English WEB) is loaded into MongoDB.

Idempotent: returns immediately if already loaded, otherwise runs the full
USFM import from bundled data. Designed for future extensibility — additional
base languages (Hebrew, Greek) slot in by adding constants and a branch.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import logging

from db_connector.connection import MongoDBConnector
from utils.usfm_parser.usfm_importer import (
    import_usfm_directory_to_mongodb,
    sync_bible_books_from_texts
)
from utils.word_index.builder import build_word_index
from constants import Collection
from .dependencies import get_db, api_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ── English constants ──────────────────────────────────────────────────────────

ENGLISH_LANGUAGE_CODE = "english"
ENGLISH_LANGUAGE_NAME = "English"

# routes/ → back_end/ → project root → data/bibles/eng-web_usfm/
BUNDLED_ENGLISH_USFM = Path(__file__).parent.parent.parent / "data" / "bibles" / "eng-web_usfm"

SUPPORTED_BASE_LANGUAGES = {ENGLISH_LANGUAGE_CODE}

# ── Pydantic models ────────────────────────────────────────────────────────────


class EnsureBaseLanguageRequest(BaseModel):
    language_code: str = "english"


class EnsureBaseLanguageResponse(BaseModel):
    success: bool
    already_loaded: bool
    language_code: str
    message: str
    verses_imported: int = 0
    verses_updated: int = 0
    books_processed: int = 0
    warnings: list[str] = []


# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post("/ensure-base-language", response_model=EnsureBaseLanguageResponse)
async def ensure_base_language(
    request: EnsureBaseLanguageRequest,
    db: MongoDBConnector = Depends(get_db)
):
    """
    Ensure the selected base language is loaded in the database.

    Idempotent — returns immediately if already loaded (fast path).
    On first run, imports ~31k verses from bundled USFM data (~30s).
    """
    if request.language_code not in SUPPORTED_BASE_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported base language: '{request.language_code}'. "
                f"Currently supported: {sorted(SUPPORTED_BASE_LANGUAGES)}"
            )
        )

    database = db.get_database()
    languages_collection = database[Collection.LANGUAGES]

    # ── Fast path: already fully loaded ───────────────────────────────────────
    existing = await languages_collection.find_one({
        "language_code": ENGLISH_LANGUAGE_CODE,
        "base_language_load_complete": True
    })
    if existing:
        logger.info("English base language already loaded — returning fast path")
        return EnsureBaseLanguageResponse(
            success=True,
            already_loaded=True,
            language_code=ENGLISH_LANGUAGE_CODE,
            message="English base language already loaded",
            verses_imported=0,
            verses_updated=0,
            books_processed=0,
            warnings=[]
        )

    # ── Validate bundled USFM path ─────────────────────────────────────────────
    if not BUNDLED_ENGLISH_USFM.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Bundled English USFM data not found at: {BUNDLED_ENGLISH_USFM}"
        )

    logger.info(f"Starting English base language import from {BUNDLED_ENGLISH_USFM}")

    try:
        result = await import_usfm_directory_to_mongodb(
            dirpath=BUNDLED_ENGLISH_USFM,
            language_code=ENGLISH_LANGUAGE_CODE,
            language_name=ENGLISH_LANGUAGE_NAME,
        )

        if result.errors:
            logger.warning(f"English import completed with errors: {result.errors}")

        total_verses = result.verses_imported + result.verses_updated

        # ── Upsert languages document ──────────────────────────────────────────
        # base_language_load_complete is written ONLY here, on full success.
        # $setOnInsert fields apply only when a new document is created.
        bible_texts = database[Collection.BIBLE_TEXTS]
        verses_verified = await bible_texts.count_documents({
            "language_code": ENGLISH_LANGUAGE_CODE,
            "human_verified": True
        })

        await languages_collection.update_one(
            {"language_code": ENGLISH_LANGUAGE_CODE},
            {
                "$set": {
                    "language_name": ENGLISH_LANGUAGE_NAME,
                    "language_code": ENGLISH_LANGUAGE_CODE,
                    "is_base_language": True,
                    "base_language_load_complete": True,
                    "total_verses": total_verses,
                    "translation_stats": {
                        "books_started": result.books_processed,
                        "books_completed": 0,
                        "verses_translated": total_verses,
                        "verses_verified": verses_verified,
                        "last_updated": datetime.utcnow()
                    },
                    "metadata.creator": "bundled_import",
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "status": "active",
                }
            },
            upsert=True
        )
        logger.info(f"English language document upserted ({total_verses} total verses)")

        # ── Non-fatal post-import steps ────────────────────────────────────────
        warnings = []

        try:
            idx = await build_word_index(db, ENGLISH_LANGUAGE_CODE)
            logger.info(f"Word index built: {idx['words_indexed']} words in {idx['duration_ms']}ms")
        except Exception as e:
            warnings.append(f"Word index build failed: {e}")
            logger.warning(f"Word index build failed (non-fatal): {e}")

        try:
            synced = await sync_bible_books_from_texts(
                ENGLISH_LANGUAGE_CODE, db
            )
            logger.info(f"bible_books sync: {synced} books")
        except Exception as e:
            warnings.append(f"Bible books sync failed: {e}")
            logger.warning(f"Bible books sync failed (non-fatal): {e}")

        message = (
            f"Imported {result.verses_imported} verses, "
            f"updated {result.verses_updated} existing verses "
            f"across {result.books_processed} books"
        )

        return EnsureBaseLanguageResponse(
            success=True,
            already_loaded=False,
            language_code=ENGLISH_LANGUAGE_CODE,
            message=message,
            verses_imported=result.verses_imported,
            verses_updated=result.verses_updated,
            books_processed=result.books_processed,
            warnings=warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error("Ensure base language (English)", e)
