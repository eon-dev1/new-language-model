# back_end/utils/usfm_parser/__init__.py
"""
USFM Parser Module

A reusable module for parsing USFM (Unified Standard Format Markers) Bible files
and importing them into MongoDB.

Usage:
    # Parse a single file
    from utils.usfm_parser import parse_usfm_file, ParsedVerse
    result = parse_usfm_file("path/to/bible.usfm")
    for verse in result.verses:
        print(f"{verse.book_name} {verse.chapter}:{verse.verse} - {verse.clean_text}")

    # Parse a directory
    from utils.usfm_parser import parse_usfm_directory
    result = parse_usfm_directory("path/to/usfm/directory/")

    # Import to MongoDB
    import asyncio
    from utils.usfm_parser import import_usfm_directory_to_mongodb
    result = asyncio.run(import_usfm_directory_to_mongodb(
        "path/to/usfm/directory/",
        language_code="english",
        translation_type="human"
    ))

Components:
    - remove_usfm_markers: Clean USFM markers from text (keeps content)
    - usfm_book_codes: USFM code to MongoDB book_code mapping
    - usfm_parser: Core parsing logic for extracting verses
    - usfm_importer: MongoDB import with batch operations
"""

# Core text cleaning
from .remove_usfm_markers import remove_usfm_markers

# Book code mapping
from .usfm_book_codes import (
    USFM_TO_BOOK_CODE,
    USFM_TO_BOOK_NAME,
    BOOK_CODE_TO_USFM,
    usfm_code_to_book_code,
    usfm_code_to_book_name,
    book_code_to_usfm_code,
    book_name_to_book_code,
    is_valid_usfm_code,
    get_all_usfm_codes,
    get_all_book_codes,
)

# Parser
from .usfm_parser import (
    ParsedVerse,
    ParseResult,
    parse_usfm_file,
    parse_usfm_directory,
    iter_usfm_verses,
)

# MongoDB importer
from .usfm_importer import (
    ImportResult,
    import_usfm_to_mongodb,
    import_usfm_directory_to_mongodb,
    update_bible_books_collection,
)

__all__ = [
    # Text cleaning
    "remove_usfm_markers",
    # Book code mapping
    "USFM_TO_BOOK_CODE",
    "USFM_TO_BOOK_NAME",
    "BOOK_CODE_TO_USFM",
    "usfm_code_to_book_code",
    "usfm_code_to_book_name",
    "book_code_to_usfm_code",
    "book_name_to_book_code",
    "is_valid_usfm_code",
    "get_all_usfm_codes",
    "get_all_book_codes",
    # Parser
    "ParsedVerse",
    "ParseResult",
    "parse_usfm_file",
    "parse_usfm_directory",
    "iter_usfm_verses",
    # MongoDB importer
    "ImportResult",
    "import_usfm_to_mongodb",
    "import_usfm_directory_to_mongodb",
    "update_bible_books_collection",
]