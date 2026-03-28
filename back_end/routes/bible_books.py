# bible_books.py
"""
Bible books endpoint for retrieving book structure by language.

Returns the list of Bible books with chapter/verse counts for a specific language.
"""

from fastapi import APIRouter, HTTPException, Path, Depends
from typing import Dict, Any
import logging
from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error
from shared.chat_config import load_config
from utils.usfm_parser.usfm_book_codes import get_all_book_codes, USFM_BOOK_DATA, BOOK_CODE_TO_USFM
from utils.bible_generator.chapter_verse_numbers import BIBLE_CHAPTER_VERSES

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/bible-books/{language}", response_model=Dict[str, Any])
async def get_bible_books(
    language: str = Path(..., description="Language code (e.g., 'english', 'kope')"),
    db: MongoDBConnector = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all Bible books for a specific language.

    Args:
        language: Language code to filter by (case-insensitive)

    Returns:
        dict: Contains:
            - language (str): The queried language code
            - books (list): List of book objects with:
                - book_name (str): Display name
                - book_code (str): Normalized code
                - total_chapters (int): Number of chapters
                - total_verses (int): Total verse count
                - translation_status (str): Progress status
            - count (int): Total number of book documents

    Raises:
        HTTPException: 404 if no books found, 500 on database error
    """
    try:
        # Normalize language code
        language_code = language.lower().replace(' ', '_').replace('-', '_')

        database = db.get_database()
        bible_books_collection = database[Collection.BIBLE_BOOKS]

        # Fetch all books for this language
        cursor = bible_books_collection.find(
            {"language_code": language_code},
            {
                "_id": 0,
                "book_name": 1,
                "book_code": 1,
                "total_chapters": 1,
                "total_verses": 1,
                "translation_status": 1,
                "metadata.testament": 1,
                "metadata.canonical_order": 1
            }
        ).sort("metadata.canonical_order", 1)

        books = await cursor.to_list(length=None)

        # If no books in bible_books collection, derive structure from bible_texts
        if not books:
            logger.info(f"No bible_books entries for {language_code}, deriving from bible_texts...")

            bible_texts = database[Collection.BIBLE_TEXTS]

            # Aggregate book structure from individual verses
            pipeline = [
                {"$match": {"language_code": language_code}},
                {"$group": {
                    "_id": "$book_code",
                    "total_verses": {"$sum": 1},
                    "chapters": {"$addToSet": "$chapter"}
                }},
                {"$project": {
                    "_id": 0,
                    "book_code": "$_id",
                    "book_name": "$_id",  # Use code as display name
                    "total_chapters": {"$size": "$chapters"},
                    "total_verses": 1,
                    "translation_status": {"$literal": "imported"}
                }},
                {"$sort": {"book_code": 1}}
            ]

            derived_cursor = bible_texts.aggregate(pipeline)
            books = await derived_cursor.to_list(length=None)

            # Sort by canonical order (Genesis → Revelation)
            canonical_order_for_sort = get_all_book_codes()
            order_map = {code: i for i, code in enumerate(canonical_order_for_sort)}
            books.sort(key=lambda b: order_map.get(b.get("book_code", ""), 999))

            if books:
                logger.info(f"Derived {len(books)} books from bible_texts for {language_code}")
            else:
                logger.warning(f"No Bible data found for language: {language_code} — will fill from English")
        else:
            logger.info(f"Retrieved {len(books)} Bible books for language: {language_code}")

        # --- English fill: always return 66 books ---

        # Fetch English books as canonical source for any gaps
        english_cursor = bible_books_collection.find(
            {"language_code": "english"},
            {
                "_id": 0,
                "book_code": 1,
                "book_name": 1,
                "total_chapters": 1,
                "total_verses": 1,
                "metadata.testament": 1,
                "metadata.canonical_order": 1,
            }
        )
        english_books = {b["book_code"]: b for b in await english_cursor.to_list(length=None)}

        # Mark all language books found above with has_data: True
        lang_books = {}
        for b in books:
            b["has_data"] = True
            lang_books[b["book_code"]] = b

        # Walk canonical order, filling gaps from English
        canonical_order = get_all_book_codes()
        dev = load_config().get("dev_features", {})
        if not dev.get("book_of_enoch"):
            canonical_order = [c for c in canonical_order if c != "1_enoch"]
        merged = []
        for book_code in canonical_order:
            if book_code in lang_books:
                merged.append(lang_books[book_code])
            elif book_code in english_books:
                eng = english_books[book_code]
                merged.append({
                    "book_code": book_code,
                    "book_name": eng["book_name"],
                    "total_chapters": eng["total_chapters"],
                    "total_verses": eng["total_verses"],
                    "translation_status": "not_started",
                    "metadata": eng.get("metadata", {}),
                    "has_data": False,
                })

        # Edge case: English bible_books also empty (unlikely dev-only scenario)
        if not english_books:
            logger.warning("English bible_books not found — using USFM display names as fallback")
            order_map = {code: i + 1 for i, code in enumerate(canonical_order)}
            for book_code in canonical_order:
                if book_code not in lang_books:
                    usfm_code = BOOK_CODE_TO_USFM.get(book_code, "")
                    display_name = USFM_BOOK_DATA.get(usfm_code, (book_code, book_code))[1]
                    total_chapters = len(BIBLE_CHAPTER_VERSES.get(display_name, []))
                    total_verses = sum(v for _, v in BIBLE_CHAPTER_VERSES.get(display_name, []))
                    canonical_pos = order_map.get(book_code, 999)
                    merged.append({
                        "book_code": book_code,
                        "book_name": display_name,
                        "total_chapters": total_chapters,
                        "total_verses": total_verses,
                        "translation_status": "not_started",
                        "metadata": {
                            "testament": "old" if canonical_pos <= 39 else "new",
                            "canonical_order": canonical_pos,
                        },
                        "has_data": False,
                    })

        return {
            "language": language_code,
            "books": merged,
            "count": len(merged)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Retrieve Bible books for {language}", e)