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
            "translation_stats": dict,
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
                ],
                "unique": True,
                "name": "verse_lookup",
            },
            {
                "keys": [("language_code", 1)],
                "name": "language_type_filter",
            },
            {
                "keys": [("book_code", 1)],
                "name": "book_type_filter",
            },
        ],
        "required_fields": {
            "language_code": str,
            "book_code": str,
            "chapter": int,
            "verse": int,
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
                ],
                "unique": True,
                "name": "book_lookup",
            },
            {
                "keys": [("language_code", 1)],
                "name": "language_type_filter",
            },
        ],
        "required_fields": {
            "language_code": str,
            "book_name": str,
            "book_code": str,
            "total_chapters": int,
            "total_verses": int,
            "chapters": list,
            "created_at": "datetime",
            "translation_status": str,
            "metadata": dict,
        },
        "optional_fields": {
            "language_name": str,
            "updated_at": "datetime",
        },
        "embedded_schema": {
            "metadata": {
                "required_fields": {
                    "testament": str,
                    "canonical_order": int,
                },
                "optional_fields": {
                    "ai_model": str,
                },
            },
            "chapters": {
                "required_fields": {
                    "chapter": int,
                    "verse_count": int,
                },
                "optional_fields": {},
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
                "keys": [("language_code", 1)],
                "unique": True,
                "name": "dict_lookup",
            }
        ],
        "required_fields": {
            "language_code": str,
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
                "keys": [("language_code", 1)],
                "unique": True,
                "name": "grammar_lookup",
            }
        ],
        "required_fields": {
            "language_code": str,
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
    "correction_log": {
        # Append-only log of AI content corrections, one document per correction event.
        # Queried by language_code with optional content_type filter, paginated by created_at DESC.
        "required": False,  # Created on-demand when first correction is logged
        "indexes": [
            {
                "keys": [("language_code", 1), ("created_at", -1)],
                "name": "language_time",
            },
            {
                "keys": [("language_code", 1), ("content_type", 1), ("created_at", -1)],
                "name": "language_type_time",
            },
        ],
        "required_fields": {
            "language_code": str,
            "content_type": str,
            "content_reference": dict,
            "original_text": str,
            "what_was_wrong": str,
            "correction": str,
            "created_at": "datetime",
        },
        "optional_fields": {},
    },
    "language_notes": {
        # One document per language containing an embedded array of free-form notes.
        # Looked up by language_code (find_one); notes updated/deleted by embedded UUID.
        "required": False,  # Created on-demand via upsert when first note is added
        "indexes": [
            {
                "keys": [("language_code", 1)],
                "unique": True,
                "name": "language_code_1",
            }
        ],
        "required_fields": {
            "language_code": str,
            "notes": list,
        },
        "optional_fields": {
            "updated_at": "datetime",
        },
        "embedded_schema": {
            "notes": {
                "required_fields": {
                    "id": str,
                    "title": str,
                    "text": str,
                    "created_at": "datetime",
                    "updated_at": "datetime",
                },
                "optional_fields": {},
            }
        },
    },
    "chat_conversations": {
        # Global (not language-scoped) chat conversations with embedded message history.
        # Listed sorted by updated_at DESC; individual conversations looked up by _id.
        "required": False,  # Created on-demand when user starts a conversation
        "indexes": [
            {
                "keys": [("updated_at", -1)],
                "name": "updated_at_desc",
            }
        ],
        "required_fields": {
            "title": str,
            "messages": list,
            "message_count": int,
            "created_at": "datetime",
            "updated_at": "datetime",
        },
        "optional_fields": {},
    },
    "word_index": {
        # Precomputed inverted index mapping words to verse locations.
        # One document per (language_code, word).
        # Built by utils/word_index/builder.py, queried by MCP tools.
        "required": False,  # Created on-demand when first build runs
        "indexes": [
            {
                "keys": [
                    ("language_code", 1),
                    ("word", 1),
                ],
                "unique": True,
                "name": "word_lookup",
            },
            {
                "keys": [
                    ("language_code", 1),
                    ("total_count", -1),
                ],
                "name": "frequency_sort",
            },
            {
                "keys": [
                    ("language_code", 1),
                    ("in_dictionary", 1),
                ],
                "name": "dictionary_gap",
            },
        ],
        "required_fields": {
            "language_code": str,
            "word": str,
            "total_count": int,
            "book_count": int,
            "chapter_count": int,
            "occurrences": list,
            "first_seen": dict,
            "in_dictionary": bool,
            "last_rebuilt": "datetime",
        },
        "optional_fields": {},
    },
    "phrase_index": {
        # Precomputed inverted index of recurring 4-grams -> verse locations.
        # One document per (language_code, phrase). Built by
        # utils/phrase_index/builder.py, queried by the get_phrase_context MCP tool.
        # Canonical phrase form: " ".join(tokenize_verse(text)) — single space,
        # no normalization beyond what the tokenizer produces. Builder and tool
        # MUST agree on this form; a mismatch silently returns zero hits.
        "required": False,  # Created on first build
        "indexes": [
            {
                "keys": [
                    ("language_code", 1),
                    ("phrase", 1),
                ],
                "unique": True,
                "name": "phrase_lookup",
            },
        ],
        "required_fields": {
            "language_code": str,
            "phrase": str,
            "n": int,
            "df": int,
            "min_word_df": int,
            "locations": list,
            "last_rebuilt": "datetime",
        },
        "optional_fields": {},
    },
}


# Collections that should NOT exist (legacy/deprecated)
# Will trigger warnings if found, but will NOT be removed
DEPRECATED_COLLECTIONS: list[str] = [
    # bible_books was moved to EXPECTED_COLLECTIONS - it IS actively used
]


# Valid patterns for field validation
BOOK_CODE_PATTERN = r"^[a-z0-9_]+$"  # lowercase with underscores
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
            "translation_stats": {
                "books_started": 66,
                "books_completed": 66,
                "verses_translated": 31102,
                "verses_verified": 31102,
                # last_updated will be set at insert time
            },
            "metadata": {
                "creator": "schema_enforcer",
                "version": "1.0",
                "source": "NET Bible",
                "description": "English base language for parallel text comparison",
            },
            # created_at will be set at insert time
        }
    ]
}
