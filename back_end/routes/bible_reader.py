# bible_reader.py
"""
Bible reader endpoints for fetching verses and updating verification status.

Provides endpoints to:
- Fetch paired verses (English + translation) for a chapter
- Update human_verified status for individual verses
"""

from fastapi import APIRouter, HTTPException, Path, Depends
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

from db_connector.connection import MongoDBConnector
from constants import Collection, TranslationType
from .dependencies import get_db, api_error

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
                "translation_type": TranslationType.HUMAN
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
                "translation_type": TranslationType.HUMAN
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
                "translation_type": TranslationType.HUMAN
            },
            {
                "$set": {
                    "human_verified": request.human_verified,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Verse not found: {language}/{book_code} {chapter}:{verse}"
            )

        logger.info(f"Updated verification for {language_code}/{normalized_book_code} {chapter}:{verse} to {request.human_verified}")

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
