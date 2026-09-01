# bible_reader.py
"""
Bible reader endpoints for fetching verses and updating verification status.

Provides endpoints to:
- Fetch paired verses (English + translation) for a chapter
- Update human_verified status for individual verses
"""

import asyncio
import re

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging

from db_connector.connection import MongoDBConnector, get_mongodb_connector
from constants import Collection
from utils.word_index.builder import build_word_index
from utils.phrase_index import scheduler as phrase_index_scheduler
from .dependencies import get_db, api_error

# Lock to prevent concurrent word index rebuilds
_rebuild_lock = asyncio.Lock()

router = APIRouter()
logger = logging.getLogger(__name__)


class VerseData(BaseModel):
    """Individual verse with paired English and translation text."""
    verse: int
    english_text: str
    translated_text: str
    human_verified: bool


class ChapterResponse(BaseModel):
    """Response containing all verses for a chapter."""
    language_code: str
    book_code: str
    chapter: int
    verses: List[VerseData]
    count: int


class VerifyVerseRequest(BaseModel):
    """Request to update verse verification status."""
    human_verified: bool


class VerifyVerseResponse(BaseModel):
    """Response confirming verification update."""
    success: bool
    language_code: str
    book_code: str
    chapter: int
    verse: int
    human_verified: bool


class UpdateVerseTextRequest(BaseModel):
    """Request to update verse translated text."""
    translated_text: str


class UpdateVerseTextResponse(BaseModel):
    """Response confirming verse text update."""
    success: bool
    language_code: str
    book_code: str
    chapter: int
    verse: int
    translated_text: str
    human_verified: bool


@router.get("/verses/{language}/{book_code}/{chapter}", response_model=ChapterResponse)
async def get_chapter_verses(
    language: str = Path(..., description="Language code (e.g., 'kope', 'french')"),
    book_code: str = Path(..., description="Book code (e.g., 'GEN', 'MAT')"),
    chapter: int = Path(..., ge=1, description="Chapter number"),
    db: MongoDBConnector = Depends(get_db)
) -> ChapterResponse:
    """
    Fetch all verses for a specific chapter with both English and translated text.

    Returns paired verses with English text on left and translation on right,
    along with human_verified status for each verse.

    Args:
        language: Target language code
        book_code: Bible book code
        chapter: Chapter number (1-based)

    Returns:
        ChapterResponse with list of verses containing both languages

    Raises:
        HTTPException: 404 if no verses found, 500 on database error
    """
    try:
        # Normalize language code
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        # Normalize book code - preserve case as stored
        normalized_book_code = book_code.strip()

        database = db.get_database()
        bible_texts = database[Collection.BIBLE_TEXTS]

        # Fetch English (base language) verses for this chapter
        english_cursor = bible_texts.find(
            {
                "language_code": "english",
                "book_code": normalized_book_code,
                "chapter": chapter,
            },
            {"_id": 0, "verse": 1, "english_text": 1}
        ).sort("verse", 1)

        english_verses = {}
        async for doc in english_cursor:
            english_verses[doc["verse"]] = doc.get("english_text", "")

        # Fetch target language verses
        target_cursor = bible_texts.find(
            {
                "language_code": language_code,
                "book_code": normalized_book_code,
                "chapter": chapter,
            },
            {"_id": 0, "verse": 1, "translated_text": 1, "human_verified": 1}
        ).sort("verse", 1)

        verses = []
        async for doc in target_cursor:
            verse_num = doc["verse"]
            verses.append(VerseData(
                verse=verse_num,
                english_text=english_verses.get(verse_num, ""),
                translated_text=doc.get("translated_text", ""),
                human_verified=doc.get("human_verified", False)
            ))

        # If no translation exists, fall back to English-only
        if not verses and english_verses:
            verses = [
                VerseData(
                    verse=verse_num,
                    english_text=text,
                    translated_text="",
                    human_verified=False,
                )
                for verse_num, text in sorted(english_verses.items())
            ]
            logger.info(
                f"No translation found for {language_code}/{normalized_book_code} ch.{chapter} "
                f"— serving English only ({len(verses)} verses)"
            )

        if not verses:
            raise HTTPException(
                status_code=404,
                detail=f"No verses found for {language}/{book_code} chapter {chapter}"
            )

        logger.info(f"Retrieved {len(verses)} verses for {language_code}/{normalized_book_code} chapter {chapter}")

        return ChapterResponse(
            language_code=language_code,
            book_code=normalized_book_code,
            chapter=chapter,
            verses=verses,
            count=len(verses)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Fetch verses for {language}/{book_code}/{chapter}", e)


@router.patch("/verses/{language}/{book_code}/{chapter}/{verse}/verify", response_model=VerifyVerseResponse)
async def update_verse_verification(
    language: str = Path(..., description="Language code"),
    book_code: str = Path(..., description="Book code"),
    chapter: int = Path(..., ge=1, description="Chapter number"),
    verse: int = Path(..., ge=1, description="Verse number"),
    request: VerifyVerseRequest = ...,
    db: MongoDBConnector = Depends(get_db)
) -> VerifyVerseResponse:
    """
    Update the human_verified status for a specific verse.

    Args:
        language: Target language code
        book_code: Bible book code
        chapter: Chapter number
        verse: Verse number
        request: Contains the new human_verified status

    Returns:
        VerifyVerseResponse confirming the update

    Raises:
        HTTPException: 404 if verse not found, 500 on database error
    """
    try:
        # Normalize language code
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        normalized_book_code = book_code.strip()

        database = db.get_database()
        bible_texts = database[Collection.BIBLE_TEXTS]

        result = await bible_texts.update_one(
            {
                "language_code": language_code,
                "book_code": normalized_book_code,
                "chapter": chapter,
                "verse": verse,
            },
            {
                "$set": {
                    "human_verified": request.human_verified,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Verse not found: {language}/{book_code} {chapter}:{verse}"
            )

        # Update verses_verified count in language document
        languages_col = database[Collection.LANGUAGES]
        increment = 1 if request.human_verified else -1
        await languages_col.update_one(
            {"language_code": language_code},
            {"$inc": {"translation_stats.verses_verified": increment}}
        )

        logger.info(f"Updated verification for {language_code}/{normalized_book_code} {chapter}:{verse} to {request.human_verified}")

        # Schedule a debounced phrase_index rebuild. English short-circuits
        # inside schedule(); no-op for base language.
        await phrase_index_scheduler.schedule(language_code)

        return VerifyVerseResponse(
            success=True,
            language_code=language_code,
            book_code=normalized_book_code,
            chapter=chapter,
            verse=verse,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Update verification for {language}/{book_code} {chapter}:{verse}", e)


@router.put("/verses/{language}/{book_code}/{chapter}/{verse}", response_model=UpdateVerseTextResponse)
async def update_verse_text(
    language: str = Path(..., description="Language code"),
    book_code: str = Path(..., description="Book code"),
    chapter: int = Path(..., ge=1, description="Chapter number"),
    verse: int = Path(..., ge=1, description="Verse number"),
    request: UpdateVerseTextRequest = ...,
    db: MongoDBConnector = Depends(get_db)
) -> UpdateVerseTextResponse:
    """
    Update the translated text for a specific verse.

    Sets human_verified=True when text is non-empty; False when text is empty
    or whitespace-only (clearing a verse un-verifies it).

    Args:
        language: Target language code
        book_code: Bible book code
        chapter: Chapter number
        verse: Verse number
        request: Contains the new translated_text

    Returns:
        UpdateVerseTextResponse confirming the update

    Raises:
        HTTPException: 404 if verse not found, 500 on database error
    """
    try:
        # Normalize language code
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        normalized_book_code = book_code.strip()

        raw_text = request.translated_text or ""
        normalized_text = raw_text.strip()
        is_cleared = normalized_text == ""
        stored_text = "" if is_cleared else raw_text
        human_verified = not is_cleared

        database = db.get_database()
        bible_texts = database[Collection.BIBLE_TEXTS]

        now = datetime.now(timezone.utc)
        await bible_texts.update_one(
            {
                "language_code": language_code,
                "book_code": normalized_book_code,
                "chapter": chapter,
                "verse": verse,
            },
            {
                "$set": {
                    "translated_text": stored_text,
                    "human_verified": human_verified,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

        logger.info(f"Updated text for {language_code}/{normalized_book_code} {chapter}:{verse}")

        # Fire-and-forget word index rebuild (non-blocking)
        # Uses global connector — the request-scoped db is closed before this task runs.
        async def _rebuild():
            async with _rebuild_lock:
                try:
                    global_db = await get_mongodb_connector()
                    await build_word_index(global_db, language_code)
                except Exception as e:
                    logger.warning(f"Word index rebuild failed (non-fatal): {e}")

        asyncio.create_task(_rebuild())

        # Schedule a debounced phrase_index rebuild. English short-circuits
        # inside schedule(); no-op for base language.
        await phrase_index_scheduler.schedule(language_code)

        return UpdateVerseTextResponse(
            success=True,
            language_code=language_code,
            book_code=normalized_book_code,
            chapter=chapter,
            verse=verse,
            translated_text=stored_text,
            human_verified=human_verified,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Update text for {language}/{book_code} {chapter}:{verse}", e)


class VerseSearchResult(BaseModel):
    """Single verse result from a cross-book text search."""
    book_code: str
    chapter: int
    verse: int
    english_text: str
    translated_text: Optional[str]


class VerseSearchResponse(BaseModel):
    """Response for verse text search across all books."""
    results: List[VerseSearchResult]
    count: int
    query: str


@router.get("/verses/{language}/search", response_model=VerseSearchResponse)
async def search_bible_verses(
    language: str = Path(..., description="Language code (e.g., 'kope')"),
    q: str = Query(..., min_length=2, max_length=200, description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    db: MongoDBConnector = Depends(get_db)
) -> VerseSearchResponse:
    """
    Search verse text across all books in both English and the target language.

    Uses two separate regex queries (English + target) merged by
    (book_code, chapter, verse) key, so a verse matching in both languages
    appears exactly once. Limit is applied to the merged output.

    Returns 200 with empty results for no matches — never 404.
    """
    try:
        # Inline normalization — matches every other handler in this file
        language_code = language.lower().replace(' ', '_').replace('-', '_')

        safe_q = re.escape(q)  # prevents 500 on regex metacharacter input (e.g. "[")
        regex_filter = {"$regex": safe_q, "$options": "i"}

        database = db.get_database()
        bible_texts = database[Collection.BIBLE_TEXTS]

        # Query 1: English docs
        english_cursor = bible_texts.find(
            {
                "language_code": "english",
                "english_text": regex_filter,
            },
            limit=limit
        )

        # Query 2: Target language docs
        target_cursor = bible_texts.find(
            {
                "language_code": language_code,
                "translated_text": regex_filter,
            },
            limit=limit
        )

        # Merge by (book_code, chapter, verse) — lowercase book_code prevents
        # case-mismatch merge failures
        results: dict = {}

        async for doc in english_cursor:
            key = (doc["book_code"].lower(), doc["chapter"], doc["verse"])
            if key not in results:
                results[key] = VerseSearchResult(
                    book_code=doc["book_code"].lower(),
                    chapter=doc["chapter"],
                    verse=doc["verse"],
                    english_text=doc.get("english_text", ""),
                    translated_text=None,
                )
            else:
                results[key].english_text = doc.get("english_text", "")

        async for doc in target_cursor:
            key = (doc["book_code"].lower(), doc["chapter"], doc["verse"])
            if key not in results:
                results[key] = VerseSearchResult(
                    book_code=doc["book_code"].lower(),
                    chapter=doc["chapter"],
                    verse=doc["verse"],
                    english_text="",
                    translated_text=doc.get("translated_text"),
                )
            else:
                # Patch only — do NOT overwrite the whole entry (would erase english_text)
                results[key].translated_text = doc.get("translated_text")

        merged = list(results.values())[:limit]
        return VerseSearchResponse(results=merged, count=len(merged), query=q)

    except Exception as e:
        raise api_error(f"Search verses for {language}", e)
