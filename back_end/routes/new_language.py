# new_language.py
"""
MongoDB endpoint to create a new language dataset.

Creates collections and documents in MongoDB for a specified language with dual-level support:
- Language metadata in 'languages' collection
- Bible books structure in 'bible_books' collection (human + LLM versions)
- Dictionary setup in 'dictionaries' collection (human + NLM versions)
- Grammar framework in 'grammar_systems' collection (human + NLM versions)
- Bible text structure in 'bible_texts' collection (human + LLM versions)

Each language (except English base) has:
1. Human-translated bible & LLM-generated bible
2. Human dictionary & NLM-generated dictionary
3. Human grammar & NLM-generated grammar
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import logging
import re
from datetime import datetime
from db_connector.connection import MongoDBConnector
from constants import Collection, TranslationType
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

    This endpoint creates the necessary collections and documents for a new language
    with dual-level support (human + AI versions):
    - Language metadata document
    - Bible book structure documents (human + LLM versions)
    - Dictionary collection setup (human + NLM versions)
    - Grammar system framework (human + NLM versions)
    - Bible text collection structure with chapters/verses (human + LLM versions)

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
                "translation_levels": {
                    "human": {
                        "books_started": 0,
                        "books_completed": 0,
                        "verses_translated": 0,
                        "last_updated": None
                    },
                    "ai": {
                        "books_started": 0,
                        "books_completed": 0,
                        "verses_translated": 0,
                        "last_updated": None,
                        "model_version": "nlm-v1.0"
                    } if not is_english else None
                },
                "total_verses": sum(sum(verses for _, verses in BIBLE_CHAPTER_VERSES[book]) for book in books),
                "metadata": {
                    "creator": "nlm_fastapi_endpoint",
                    "version": "1.0",
                    "description": f"Biblical translation project for {language}",
                    "dual_level_support": not is_english
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
        
        # 2. Create Bible Books Structure (Human + AI versions)
        bible_books_collection = database[Collection.BIBLE_BOOKS]
        collections_touched.add(Collection.BIBLE_BOOKS)
        
        translation_types = [TranslationType.HUMAN] if is_english else [TranslationType.HUMAN, TranslationType.AI]
        
        for book_name in books:
            if book_name not in BIBLE_CHAPTER_VERSES:
                logger.warning(f"Chapter/verse data not found for book: {book_name}")
                continue
                
            book_code = book_name.lower().replace(' ', '_')
            
            for translation_type in translation_types:
                # Check if book already exists for this language and type
                existing_book = await bible_books_collection.find_one({
                    "language_code": language_code,
                    "book_code": book_code,
                    "translation_type": translation_type
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
                        "translation_type": translation_type,
                        "total_chapters": len(BIBLE_CHAPTER_VERSES[book_name]),
                        "total_verses": sum(verses for _, verses in BIBLE_CHAPTER_VERSES[book_name]),
                        "chapters": chapters_data,
                        "created_at": datetime.utcnow(),
                        "translation_status": "not_started",
                        "metadata": {
                            "testament": "old" if books.index(book_name) < 39 else "new",
                            "canonical_order": books.index(book_name) + 1,
                            "translator_type": "human" if translation_type == TranslationType.HUMAN else "ai",
                            "ai_model": "nlm-v1.0" if translation_type == TranslationType.AI else None
                        }
                    }
                    
                    await bible_books_collection.insert_one(book_doc)
                    documents_created += 1
        
        logger.info(f"Created {len(books) * len(translation_types)} Bible book documents for {language}")
        
        # 3. Create Dictionary Framework (Human + NLM versions)
        dictionaries_collection = database[Collection.DICTIONARIES]
        collections_touched.add(Collection.DICTIONARIES)
        
        for translation_type in translation_types:
            existing_dict = await dictionaries_collection.find_one({
                "language_code": language_code,
                "translation_type": translation_type
            })
            
            if not existing_dict:
                type_label = "Human" if translation_type == TranslationType.HUMAN else "NLM-Generated"
                dictionary_doc = {
                    "language_code": language_code,
                    "language_name": language,
                    "translation_type": translation_type,
                    "dictionary_name": f"{language} {type_label} Dictionary",
                    "entries": [],
                    "entry_count": 0,
                    "created_at": datetime.utcnow(),
                    "categories": [
                        "noun", "verb", "adjective", "adverb", "preposition", 
                        "conjunction", "interjection", "pronoun", "article", "other"
                    ],
                    "metadata": {
                        "description": f"{type_label}  dictionary for {language} translation work",
                        "version": "1.0",
                        "status": "active",
                        "generation_method": translation_type,
                        "ai_model": "nlm-v1.0" if translation_type == TranslationType.AI else None
                    }
                }
                await dictionaries_collection.insert_one(dictionary_doc)
                documents_created += 1
                logger.info(f"Created {type_label.lower()} dictionary framework for {language}")
        
        # 4. Create Grammar System Framework (Human + NLM versions)
        grammar_collection = database[Collection.GRAMMAR_SYSTEMS]
        collections_touched.add(Collection.GRAMMAR_SYSTEMS)
        
        for translation_type in translation_types:
            existing_grammar = await grammar_collection.find_one({
                "language_code": language_code,
                "translation_type": translation_type
            })
            
            if not existing_grammar:
                type_label = "Human" if translation_type == TranslationType.HUMAN else "NLM-Generated"
                grammar_doc = {
                    "language_code": language_code,
                    "language_name": language,
                    "translation_type": translation_type,
                    "grammar_system_name": f"{language} {type_label} Grammar System",
                    "created_at": datetime.utcnow(),
                    "categories": {
                        "phonology": {
                            "description": "Sound system and pronunciation rules",
                            "subcategories": ["consonants", "vowels", "tone", "stress", "phonotactics"],
                            "notes": [],
                            "examples": [],
                            "ai_confidence": None if translation_type == TranslationType.HUMAN else 0.0
                        },
                        "morphology": {
                            "description": "Word structure and formation",
                            "subcategories": ["noun_morphology", "verb_morphology", "adjective_morphology", "derivation"],
                            "notes": [],
                            "examples": [],
                            "ai_confidence": None if translation_type == TranslationType.HUMAN else 0.0
                        },
                        "syntax": {
                            "description": "Sentence structure and word order",
                            "subcategories": ["word_order", "clause_structure", "phrase_structure", "agreement"],
                            "notes": [],
                            "examples": [],
                            "ai_confidence": None if translation_type == TranslationType.HUMAN else 0.0
                        },
                        "semantics": {
                            "description": "Meaning and interpretation",
                            "subcategories": ["lexical_semantics", "compositional_semantics", "pragmatics"],
                            "notes": [],
                            "examples": [],
                            "ai_confidence": None if translation_type == TranslationType.HUMAN else 0.0
                        },
                        "discourse": {
                            "description": "Text-level organization and coherence",
                            "subcategories": ["paragraph_structure", "narrative_patterns", "discourse_markers"],
                            "notes": [],
                            "examples": [],
                            "ai_confidence": None if translation_type == TranslationType.HUMAN else 0.0
                        }
                    },
                    "metadata": {
                        "version": "1.0",
                        "status": "active",
                        "description": f"{type_label} comprehensive grammar system for {language}",
                        "generation_method": translation_type,
                        "ai_model": "nlm-v1.0" if translation_type == TranslationType.AI else None,
                        "human_review_status": "pending" if translation_type == TranslationType.AI else "n/a"
                    }
                }
                await grammar_collection.insert_one(grammar_doc)
                documents_created += 1
                logger.info(f"Created {type_label.lower()} grammar system framework for {language}")
        
        # 5. Create Bible Texts Collection Structure (Human + LLM versions)
        bible_texts_collection = database[Collection.BIBLE_TEXTS]
        collections_touched.add(Collection.BIBLE_TEXTS)
        
        # Create indexes for efficient querying (includes translation_type)
        await bible_texts_collection.create_index([
            ("language_code", 1),
            ("book_code", 1),
            ("chapter", 1),
            ("verse", 1),
            ("translation_type", 1)
        ], unique=True)
        
        # Create separate indexes for common queries
        await bible_texts_collection.create_index([("language_code", 1), ("translation_type", 1)])
        await bible_texts_collection.create_index([("book_code", 1), ("translation_type", 1)])
        
        # Log indexing completion
        existing_texts_count = await bible_texts_collection.count_documents({"language_code": language_code})
        if existing_texts_count == 0:
            logger.info(f"Bible texts collection indexed and ready for {language} (human + AI versions)")
        
        # Calculate totals
        total_bible_documents = len(books) * len(translation_types)
        total_dictionary_documents = len(translation_types)
        total_grammar_documents = len(translation_types)
        
        return {
            "success": "true",
            "message": f"Successfully created MongoDB collections and documents for language '{language}' with dual-level support",
            "language_code": language_code,
            "is_base_language": str(is_english),
            "translation_levels": translation_types,
            "documents_created": str(documents_created),
            "collections_touched": list(collections_touched),
            "bible_books_count": str(len(books)),
            "bible_documents_created": str(total_bible_documents),
            "dictionary_documents_created": str(total_dictionary_documents), 
            "grammar_documents_created": str(total_grammar_documents),
            "total_verses_framework": str(sum(sum(verses for _, verses in BIBLE_CHAPTER_VERSES[book]) 
                                            for book in books if book in BIBLE_CHAPTER_VERSES))
        }

    except Exception as e:
        raise api_error(f"Create language '{language}'", e)