"""
Schema Definition - Single Source of Truth for MongoDB Schema

============================================================================
AUTHORITATIVE SCHEMA DEFINITION
This file is the single source of truth for MongoDB schema.
docs/database.md should be updated to match this, not vice versa.
============================================================================
"""

from typing import Any

# Schema version for future migration support (semver format)
SCHEMA_VERSION = "1.0.0"

# Type aliases for clarity
FieldType = type | str  # str for special types like "datetime"


EXPECTED_COLLECTIONS: dict[str, dict[str, Any]] = {
    "languages": {
        "required": True,
        "indexes": [
            {"keys": [("language_code", 1)], "unique": True, "name": "language_code_1"}
        ],
        "required_fields": {
            "language_name": str,
            "language_code": str,
            "is_base_language": bool,
            "created_at": "datetime",
            "status": str,
            "translation_levels": dict,
            "metadata": dict,
        },
        "optional_fields": {
            "updated_at": "datetime",
            "bible_books_count": int,
            "total_verses": int,
        },
    },
    "bible_texts": {
        "required": True,
        "indexes": [
            {
                "keys": [
                    ("language_code", 1),
                    ("book_code", 1),
                    ("chapter", 1),
                    ("verse", 1),
                    ("translation_type", 1),
                ],
                "unique": True,
                "name": "verse_lookup",
            },
            {
                "keys": [("language_code", 1), ("translation_type", 1)],
                "name": "language_type_filter",
            },
            {
                "keys": [("book_code", 1), ("translation_type", 1)],
                "name": "book_type_filter",
            },
        ],
        "required_fields": {
            "language_code": str,
            "book_code": str,
            "chapter": int,
            "verse": int,
            "translation_type": str,
            "created_at": "datetime",
        },
        # Fields that vary by language type (simpler than DSL)
        "english_only_fields": ["english_text"],
        "non_english_only_fields": ["translated_text", "human_verified"],
        "optional_fields": {
            "updated_at": "datetime",
            "footnotes": list,
            "language_name": str,
            "english_text": str,
            "translated_text": str,
            "human_verified": bool,
        },
    },
    "bible_books": {
        # Language-specific book metadata with embedded chapters/verses
        # Created by new_language.py, updated by usfm_importer.py
        # Queried by bible_books.py route for frontend book lists
        "required": True,
        "indexes": [
            {
                "keys": [
                    ("language_code", 1),
                    ("book_code", 1),
                    ("translation_type", 1),
                ],
                "unique": True,
                "name": "book_lookup",
            },
            {
                "keys": [("language_code", 1), ("translation_type", 1)],
                "name": "language_type_filter",
            },
        ],
        "required_fields": {
            "language_code": str,
            "language_name": str,
            "book_name": str,
            "book_code": str,
            "translation_type": str,
            "total_chapters": int,
            "total_verses": int,
            "chapters": list,
            "created_at": "datetime",
            "translation_status": str,
            "metadata": dict,
        },
        "optional_fields": {
            "updated_at": "datetime",
        },
        "embedded_schema": {
            "metadata": {
                "required_fields": {
                    "testament": str,
                    "canonical_order": int,
                    "translator_type": str,
                },
                "optional_fields": {
                    "ai_model": str,
                },
            },
        },
    },
    "base_structure_bible": {
        # Canonical Bible structure - 31,102 verse placeholders (no text content)
        # Used by generator scripts for seeding new databases
        # NOT queried by routes - for language-specific data, use bible_books
        "required": True,
        "indexes": [
            {
                "keys": [("book", 1), ("chapter", 1), ("verse", 1)],
                "unique": True,
                "name": "verse_structure",
            },
            {"keys": [("book_order", 1)], "name": "canonical_order"},
        ],
        "required_fields": {
            "book": str,
            "chapter": int,
            "verse": int,
            "book_order": int,  # 1-66, validated separately
            "testament": str,
            "language_code": str,  # Always "base"
            "is_base_structure": bool,
        },
        "optional_fields": {
            "text": str,
            "translation": str,
            "created_at": "datetime",
            "updated_at": "datetime",
        },
    },
    "dictionaries": {
        "required": True,
        "indexes": [
            {
                "keys": [("language_code", 1), ("translation_type", 1)],
                "unique": True,
                "name": "dict_lookup",
            }
        ],
        "required_fields": {
            "language_code": str,
            "translation_type": str,
            "dictionary_name": str,
            "entries": list,
            "entry_count": int,
            "created_at": "datetime",
        },
        "optional_fields": {
            "language_name": str,
            "categories": list,
            "metadata": dict,
        },
        "embedded_schema": {
            "entries": {
                "required_fields": {"word": str, "definition": str},
                "optional_fields": {
                    "part_of_speech": str,
                    "etymology": str,
                    "examples": list,
                    "human_verified": bool,
                    "created_at": "datetime",
                    "updated_at": "datetime",
                },
            }
        },
    },
    "grammar_systems": {
        "required": True,
        "indexes": [
            {
                "keys": [("language_code", 1), ("translation_type", 1)],
                "unique": True,
                "name": "grammar_lookup",
            }
        ],
        "required_fields": {
            "language_code": str,
            "translation_type": str,
            "grammar_system_name": str,
            "categories": dict,
            "created_at": "datetime",
        },
        "optional_fields": {
            "language_name": str,
            "metadata": dict,
        },
        "category_names": [
            "phonology",
            "morphology",
            "syntax",
            "semantics",
            "discourse",
        ],
    },
}


# Collections that should NOT exist (legacy/deprecated)
# Will trigger warnings if found, but will NOT be removed
DEPRECATED_COLLECTIONS: list[str] = [
    # bible_books was moved to EXPECTED_COLLECTIONS - it IS actively used
]


# Valid patterns for field validation
BOOK_CODE_PATTERN = r"^[a-z0-9_]+$"  # lowercase with underscores
VALID_TRANSLATION_TYPES = {"human", "ai"}
BOOK_ORDER_RANGE = (1, 66)  # Canonical Bible book order


# Required seed data - documents that must exist for the system to function
# The schema enforcer will insert these if missing during --enforce mode
REQUIRED_SEED_DATA: dict[str, list[dict[str, Any]]] = {
    "languages": [
        {
            # English is the base language - required for parallel text comparison
            # and as the reference translation for all other languages
            "language_code": "english",
            "language_name": "English",
            "is_base_language": True,
            "status": "active",
            "bible_books_count": 66,
            "total_verses": 31102,
            "translation_levels": {
                "human": {
                    "books_started": 66,
                    "books_completed": 66,
                    "verses_translated": 31102,
                    # last_updated will be set at insert time
                }
                # NO "ai" key - English is the source, not a target for AI translation
            },
            "metadata": {
                "creator": "schema_enforcer",
                "version": "1.0",
                "source": "NET Bible",
                "description": "English base language for parallel text comparison",
                "dual_level_support": False,
            },
            # created_at will be set at insert time
        }
    ]
}
