# new_language.py
"""
MongoDB endpoint to create a new language dataset.

Creates collections and documents in MongoDB for a specified language:
- Language metadata in 'languages' collection
- Bible books structure in 'bible_books' collection (one per book)
- Dictionary setup in 'dictionaries' collection (one per language)
- Grammar framework in 'grammar_systems' collection (one per language)
- Bible text indexes in 'bible_texts' collection
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import logging
import re
from datetime import datetime
from db_connector.connection import MongoDBConnector
from constants import Collection
from utils.bible_generator.chapter_verse_numbers import BIBLE_CHAPTER_VERSES, get_all_books
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/new-language", response_model=Dict[str, str])
async def create_new_language_mongodb(
    language: str,
    db: MongoDBConnector = Depends(get_db)
):
    """
    Create a new language dataset in MongoDB for biblical translation work.

    This endpoint creates the necessary collections and documents for a new language:
    - Language metadata document
    - Bible book structure documents (one per book)
    - Dictionary collection setup (one per language)
    - Grammar system framework (one per language)
    - Bible text collection indexes

    Args:
        language (str): The language name (e.g., 'Kope').

    Returns:
        dict: A success message with details of created collections and documents.

    Raises:
        HTTPException: 400 if invalid language name, 500 on failure.
    """
    if not re.match(r'^[a-zA-Z0-9_ -]+$', language):
        logger.warning(f"Invalid language name attempted: {language}")
        raise HTTPException(status_code=400, detail="Invalid language name. Use alphanumeric, spaces, hyphens, or underscores only.")

    language_code = language.lower().replace(' ', '_').replace('-', '_')
    is_english = language_code == "english"
    logger.info(f"Initiating MongoDB setup for language: {language}, code: {language_code}, is_english: {is_english}")

    try:
        database = db.get_database()

        # Get Bible books data
        books = get_all_books()
        if not books:
            raise ValueError("Failed to retrieve Bible book names")

        documents_created = 0
        collections_touched = set()

        # 1. Create/Update Language Metadata
        languages_collection = database[Collection.LANGUAGES]
        collections_touched.add(Collection.LANGUAGES)

        # Check if language already exists
        existing_language = await languages_collection.find_one({"language_code": language_code})
        if not existing_language:
            language_doc = {
                "language_name": language,
                "language_code": language_code,
                "is_base_language": is_english,
                "created_at": datetime.utcnow(),
                "status": "active",
                "bible_books_count": len(books),
                "translation_stats": {
                    "books_started": 0,
                    "books_completed": 0,
                    "verses_translated": 0,
                    "verses_verified": 0,
                    "last_updated": None
                },
                "total_verses": sum(sum(verses for _, verses in BIBLE_CHAPTER_VERSES[book]) for book in books),
                "metadata": {
                    "creator": "nlm_fastapi_endpoint",
                    "version": "1.0",
                    "description": f"Biblical translation project for {language}",
                }
            }
            await languages_collection.insert_one(language_doc)
            documents_created += 1
            logger.info(f"Created language metadata document for {language}")
        else:
            logger.info(f"Language {language} already exists, updating metadata")
            await languages_collection.update_one(
                {"language_code": language_code},
                {"$set": {"updated_at": datetime.utcnow(), "status": "active"}}
            )

        # 2. Create Bible Books Structure (one per book)
        bible_books_collection = database[Collection.BIBLE_BOOKS]
        collections_touched.add(Collection.BIBLE_BOOKS)

        for book_name in books:
            if book_name not in BIBLE_CHAPTER_VERSES:
                logger.warning(f"Chapter/verse data not found for book: {book_name}")
                continue

            book_code = book_name.lower().replace(' ', '_')

            # Check if book already exists for this language
            existing_book = await bible_books_collection.find_one({
                "language_code": language_code,
                "book_code": book_code,
            })

            if not existing_book:
                chapters_data = []
                for chapter_num, verse_count in BIBLE_CHAPTER_VERSES[book_name]:
                    chapters_data.append({
                        "chapter_number": chapter_num,
                        "verse_count": verse_count,
                        "verses": [{"verse_number": v, "english_text": "", "translated_text": "", "comments": ""}
                                 for v in range(1, verse_count + 1)]
                    })

                book_doc = {
                    "language_code": language_code,
                    "language_name": language,
                    "book_name": book_name,
                    "book_code": book_code,
                    "total_chapters": len(BIBLE_CHAPTER_VERSES[book_name]),
                    "total_verses": sum(verses for _, verses in BIBLE_CHAPTER_VERSES[book_name]),
                    "chapters": chapters_data,
                    "created_at": datetime.utcnow(),
                    "translation_status": "not_started",
                    "metadata": {
                        "testament": "old" if books.index(book_name) < 39 else "new",
                        "canonical_order": books.index(book_name) + 1,
                    }
                }

                await bible_books_collection.insert_one(book_doc)
                documents_created += 1

        logger.info(f"Created {len(books)} Bible book documents for {language}")

        # 3. Create Dictionary Framework (one per language)
        dictionaries_collection = database[Collection.DICTIONARIES]
        collections_touched.add(Collection.DICTIONARIES)

        existing_dict = await dictionaries_collection.find_one({
            "language_code": language_code,
        })

        if not existing_dict:
            dictionary_doc = {
                "language_code": language_code,
                "language_name": language,
                "dictionary_name": f"{language} Dictionary",
                "entries": [],
                "entry_count": 0,
                "created_at": datetime.utcnow(),
                "categories": [
                    "noun", "verb", "adjective", "adverb", "preposition",
                    "conjunction", "interjection", "pronoun", "article", "other"
                ],
                "metadata": {
                    "description": f"Dictionary for {language} translation work",
                    "version": "1.0",
                    "status": "active",
                }
            }
            await dictionaries_collection.insert_one(dictionary_doc)
            documents_created += 1
            logger.info(f"Created dictionary framework for {language}")

        # 4. Create Grammar System Framework (one per language)
        grammar_collection = database[Collection.GRAMMAR_SYSTEMS]
        collections_touched.add(Collection.GRAMMAR_SYSTEMS)

        existing_grammar = await grammar_collection.find_one({
            "language_code": language_code,
        })

        if not existing_grammar:
            grammar_doc = {
                "language_code": language_code,
                "language_name": language,
                "grammar_system_name": f"{language} Grammar System",
                "created_at": datetime.utcnow(),
                "categories": {
                    "phonology": {
                        "description": "Sound system and pronunciation rules",
                        "subcategories": ["consonants", "vowels", "tone", "stress", "phonotactics"],
                        "notes": [],
                        "examples": [],
                        "ai_confidence": None,
                        "human_verified": False,
                    },
                    "morphology": {
                        "description": "Word structure and formation",
                        "subcategories": ["noun_morphology", "verb_morphology", "adjective_morphology", "derivation"],
                        "notes": [],
                        "examples": [],
                        "ai_confidence": None,
                        "human_verified": False,
                    },
                    "syntax": {
                        "description": "Sentence structure and word order",
                        "subcategories": ["word_order", "clause_structure", "phrase_structure", "agreement"],
                        "notes": [],
                        "examples": [],
                        "ai_confidence": None,
                        "human_verified": False,
                    },
                    "semantics": {
                        "description": "Meaning and interpretation",
                        "subcategories": ["lexical_semantics", "compositional_semantics", "pragmatics"],
                        "notes": [],
                        "examples": [],
                        "ai_confidence": None,
                        "human_verified": False,
                    },
                    "discourse": {
                        "description": "Text-level organization and coherence",
                        "subcategories": ["paragraph_structure", "narrative_patterns", "discourse_markers"],
                        "notes": [],
                        "examples": [],
                        "ai_confidence": None,
                        "human_verified": False,
                    }
                },
                "metadata": {
                    "version": "1.0",
                    "status": "active",
                    "description": f"Comprehensive grammar system for {language}",
                }
            }
            await grammar_collection.insert_one(grammar_doc)
            documents_created += 1
            logger.info(f"Created grammar system framework for {language}")

        # 5. Ensure Bible Texts Collection indexes exist
        bible_texts_collection = database[Collection.BIBLE_TEXTS]
        collections_touched.add(Collection.BIBLE_TEXTS)

        await bible_texts_collection.create_index([
            ("language_code", 1),
            ("book_code", 1),
            ("chapter", 1),
            ("verse", 1),
        ], unique=True)

        await bible_texts_collection.create_index([("language_code", 1)])
        await bible_texts_collection.create_index([("book_code", 1)])

        existing_texts_count = await bible_texts_collection.count_documents({"language_code": language_code})
        if existing_texts_count == 0:
            logger.info(f"Bible texts collection indexed and ready for {language}")

        return {
            "success": "true",
            "message": f"Successfully created MongoDB collections and documents for language '{language}'",
            "language_code": language_code,
            "is_base_language": str(is_english),
            "documents_created": str(documents_created),
            "collections_touched": str(list(collections_touched)),
            "bible_books_count": str(len(books)),
            "total_verses_framework": str(sum(sum(verses for _, verses in BIBLE_CHAPTER_VERSES[book])
                                            for book in books if book in BIBLE_CHAPTER_VERSES))
        }

    except Exception as e:
        raise api_error(f"Create language '{language}'", e)