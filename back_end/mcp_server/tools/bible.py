"""
Bible tools for MCP server.

Tools:
- list_bible_books: Get all books for a language from bible_books collection
- get_chapter: Get all verses for a chapter (handles English vs non-English)
- get_bible_chunk: Paginated verse access for large text processing
- save_bible_batches: Save multiple batches of verses to files in one call
- get_parallel_verses: Fetch verses across multiple languages for side-by-side comparison
"""

import re
from collections import defaultdict
from math import ceil
from typing import Any

from mcp_server.tools.base import (
    ToolError,
    error_response,
    success_response,
    validate_language,
    validate_translation_type,
    validate_book_code,
    save_result_to_file,
    VALID_FILENAME_PATTERN,
)


async def list_bible_books(
    db, language_code: str, translation_type: str | None = None
) -> dict[str, Any]:
    """
    Get all books for a language from bible_books collection.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get books for
        translation_type: Optional filter ("human" or "ai")

    Returns:
        {
            "books": [{code, name, chapter_count, testament, book_order, translation_type}],
            "count": int
        }
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate translation type if provided
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # Build query
    query = {"language_code": language_code.lower()}
    if translation_type:
        query["translation_type"] = translation_type

    # Query bible_books collection
    bible_books = db.get_collection("bible_books")
    cursor = bible_books.find(query)
    cursor = cursor.sort("metadata.canonical_order", 1)  # Sort by canonical order
    docs = await cursor.to_list(length=None)

    books = []
    for doc in docs:
        metadata = doc.get("metadata", {})
        books.append(
            {
                "code": doc["book_code"],
                "name": doc["book_name"],
                "chapter_count": doc["total_chapters"],
                "testament": metadata.get("testament"),
                "book_order": metadata.get("canonical_order"),
                "translation_type": doc["translation_type"],
            }
        )

    return success_response({"books": books, "count": len(books)})


async def get_chapter(
    db,
    language_code: str,
    book_code: str,
    chapter: int,
    translation_type: str | None = None,
) -> dict[str, Any]:
    """
    Get all verses for a chapter.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get verses for
        book_code: Book code (e.g., "genesis", "1_chronicles")
        chapter: Chapter number
        translation_type: Optional filter ("human" or "ai")

    Returns:
        {
            "verses": [{verse, text, human_verified?}],
            "count": int
        }

    Notes:
        - English verses have no human_verified field
        - Non-English verses include human_verified
        - Text field is normalized from english_text or translated_text
    """
    # Validate language exists
    try:
        lang_doc = await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate and normalize book code
    try:
        book_code = validate_book_code(book_code)
    except ToolError as e:
        return error_response(e)

    # Validate translation type
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # Check if language is English (special case)
    is_english = lang_doc.get("is_base_language", False)

    # Build query
    query = {
        "language_code": language_code.lower(),
        "book_code": book_code,
        "chapter": chapter,
    }
    if translation_type:
        query["translation_type"] = translation_type

    # Query bible_texts collection
    bible_texts = db.get_collection("bible_texts")
    cursor = bible_texts.find(query)
    cursor = cursor.sort("verse", 1)  # Sort by verse number
    docs = await cursor.to_list(length=None)

    # Check if chapter exists (has any verses)
    if not docs:
        # Check if book exists at all
        book_query = {"language_code": language_code.lower(), "book_code": book_code}
        book_count = await bible_texts.count_documents(book_query)

        if book_count == 0:
            return error_response(
                ToolError(
                    "not_found",
                    f"Book '{book_code}' not found for language '{language_code}'",
                    {"language_code": language_code, "book_code": book_code},
                )
            )
        else:
            return error_response(
                ToolError(
                    "not_found",
                    f"Chapter {chapter} not found in '{book_code}'",
                    {"book_code": book_code, "chapter": chapter},
                )
            )

    verses = []
    for doc in docs:
        # Normalize text field based on language
        if is_english:
            text = doc.get("english_text", "")
        else:
            text = doc.get("translated_text", "")

        verse_data = {
            "verse": doc["verse"],
            "text": text,
        }

        # Include human_verified only for non-English
        if not is_english:
            verse_data["human_verified"] = doc.get("human_verified", False)

        verses.append(verse_data)

    return success_response({"verses": verses, "count": len(verses)})


async def get_bible_chunk(
    db,
    language_code: str,
    book_code: str | None = None,
    offset: int = 0,
    limit: int = 100,
    translation_type: str | None = None,
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated verses for large text processing.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get verses for
        book_code: Optional book filter
        offset: Number of verses to skip (default 0)
        limit: Maximum verses to return (default 100, max 500)
        translation_type: Optional filter ("human" or "ai")
        save_to_file: Optional filename to save results to temp_files/ directory.
                      If provided, returns {saved_to, record_count} instead of full data.

    Returns:
        If save_to_file is None:
            {
                "verses": [{book_code, chapter, verse, text}],
                "total": int,
                "offset": int,
                "limit": int
            }
        If save_to_file is provided:
            {
                "saved_to": "/absolute/path/to/file.json",
                "record_count": int,
                "filename": "file.json"
            }
    """
    # Validate language exists
    try:
        lang_doc = await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate book code if provided
    if book_code:
        try:
            book_code = validate_book_code(book_code)
        except ToolError as e:
            return error_response(e)

    # Validate translation type
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # Enforce limit max
    limit = min(limit, 500)

    # Check if language is English
    is_english = lang_doc.get("is_base_language", False)

    # Build query
    query = {"language_code": language_code.lower()}
    if book_code:
        query["book_code"] = book_code
    if translation_type:
        query["translation_type"] = translation_type

    # Query bible_texts collection
    bible_texts = db.get_collection("bible_texts")

    # Get total count
    total = await bible_texts.count_documents(query)

    # Get paginated results
    cursor = bible_texts.find(query)
    cursor = cursor.sort([("book_code", 1), ("chapter", 1), ("verse", 1)])
    cursor = cursor.skip(offset)
    cursor = cursor.limit(limit)
    docs = await cursor.to_list(length=None)

    verses = []
    for doc in docs:
        # Normalize text field
        if is_english:
            text = doc.get("english_text", "")
        else:
            text = doc.get("translated_text", "")

        verses.append(
            {
                "book_code": doc["book_code"],
                "chapter": doc["chapter"],
                "verse": doc["verse"],
                "text": text,
            }
        )

    result = {
        "verses": verses,
        "total": total,
        "offset": offset,
        "limit": limit,
    }

    # Save to file if requested
    if save_to_file is not None:
        try:
            file_result = save_result_to_file(
                result,
                filename=save_to_file,
                prefix=f"{language_code}_verses",
            )
            return success_response(file_result)
        except ToolError as e:
            return error_response(e)

    return success_response(result)


async def save_bible_batches(
    db,
    language_code: str,
    batch_size: int = 500,
    batch_start: int = 1,
    batch_end: int | None = None,
    book_code: str | None = None,
    translation_type: str | None = None,
    filename_prefix: str | None = None,
) -> dict[str, Any]:
    """
    Save multiple batches of Bible verses to files in a single tool call.

    Solves the "N batches = N approvals" problem by saving all batches with one approval.

    Args:
        db: MongoDBConnector instance
        language_code: Language to export (e.g., 'bughotu')
        batch_size: Verses per batch (1-500, default 500)
        batch_start: First batch number, 1-indexed (default 1)
        batch_end: Last batch number inclusive (None = all remaining)
        book_code: Optional book filter
        translation_type: Optional 'human' or 'ai' filter
        filename_prefix: Prefix for files (default: '{lang}_batch')

    Returns:
        {
            "batches_saved": int,
            "files": [{batch, filename, saved_to, record_count}],
            "verses_saved": int,
            "first_batch": int,
            "last_batch": int,
            "total_batches_available": int
        }
    """
    # === Phase 1: Parameter Validation (no DB calls) ===

    # Validate batch_size (1-500)
    if not (1 <= batch_size <= 500):
        return error_response(
            ToolError(
                "invalid_input",
                "batch_size must be 1-500",
                {"batch_size": batch_size},
            )
        )

    # Validate batch_start (>= 1, 1-indexed)
    if batch_start < 1:
        return error_response(
            ToolError(
                "invalid_input",
                "batch_start must be >= 1",
                {"batch_start": batch_start},
            )
        )

    # Validate explicit batch range (start > end is invalid)
    if batch_end is not None and batch_start > batch_end:
        return error_response(
            ToolError(
                "invalid_input",
                "batch_start cannot be greater than batch_end",
                {"batch_start": batch_start, "batch_end": batch_end},
            )
        )

    # Validate filename_prefix if provided (alphanumeric, underscore, hyphen)
    # Normalize empty/whitespace prefix to None (use default)
    if filename_prefix is not None:
        filename_prefix = filename_prefix.strip() or None

    if filename_prefix is not None and not re.match(VALID_FILENAME_PATTERN, filename_prefix):
        return error_response(
            ToolError(
                "invalid_input",
                f"Invalid filename_prefix '{filename_prefix}'. Use only letters, numbers, underscore, hyphen.",
                {"filename_prefix": filename_prefix},
            )
        )

    # === Phase 2: Data Validation (DB calls) ===

    # Validate language exists
    try:
        lang_doc = await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate book code if provided
    if book_code:
        try:
            book_code = validate_book_code(book_code)
        except ToolError as e:
            return error_response(e)

    # Validate translation type
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # === Phase 3: Count and Calculate ===

    is_english = lang_doc.get("is_base_language", False)

    # Build query
    query = {"language_code": language_code.lower()}
    if book_code:
        query["book_code"] = book_code
    if translation_type:
        query["translation_type"] = translation_type

    # Count total verses
    bible_texts = db.get_collection("bible_texts")
    total_verses = await bible_texts.count_documents(query)

    # Calculate total batches
    total_batches = ceil(total_verses / batch_size) if total_verses > 0 else 0

    # Handle empty result (0 verses)
    if total_batches == 0:
        return success_response({
            "batches_saved": 0,
            "files": [],
            "verses_saved": 0,
            "first_batch": 0,
            "last_batch": 0,
            "total_batches_available": 0,
        })

    # Resolve batch_end (None → all, clamp if > total)
    resolved_end = batch_end if batch_end is not None else total_batches
    resolved_end = min(resolved_end, total_batches)

    # Handle start > total_batches (empty result, not error)
    if batch_start > total_batches:
        return success_response({
            "batches_saved": 0,
            "files": [],
            "verses_saved": 0,
            "first_batch": batch_start,
            "last_batch": batch_start,
            "total_batches_available": total_batches,
        })

    # === Phase 4: Loop and Save ===

    prefix = filename_prefix or f"{language_code.lower()}_batch"
    files = []
    total_saved = 0

    for batch_num in range(batch_start, resolved_end + 1):
        # Calculate offset (1-indexed batch → 0-indexed offset)
        offset = (batch_num - 1) * batch_size

        # Query verses for this batch
        cursor = bible_texts.find(query)
        cursor = cursor.sort([("book_code", 1), ("chapter", 1), ("verse", 1)])
        cursor = cursor.skip(offset)
        cursor = cursor.limit(batch_size)
        docs = await cursor.to_list(length=None)

        # Build verse list
        verses = []
        for doc in docs:
            if is_english:
                text = doc.get("english_text", "")
            else:
                text = doc.get("translated_text", "")

            verses.append({
                "book_code": doc["book_code"],
                "chapter": doc["chapter"],
                "verse": doc["verse"],
                "text": text,
            })

        # Build result structure for this batch
        batch_result = {
            "verses": verses,
            "batch": batch_num,
            "offset": offset,
            "limit": batch_size,
        }

        # Save to file with zero-padded batch number
        filename = f"{prefix}_{batch_num:03d}"
        try:
            file_info = save_result_to_file(batch_result, filename=filename)
            files.append({
                "batch": batch_num,
                "filename": file_info["filename"],
                "saved_to": file_info["saved_to"],
                "record_count": len(verses),
            })
            total_saved += len(verses)
        except ToolError as e:
            return error_response(e)

    # === Phase 5: Return Summary ===

    return success_response({
        "batches_saved": len(files),
        "files": files,
        "verses_saved": total_saved,
        "first_batch": batch_start,
        "last_batch": resolved_end,
        "total_batches_available": total_batches,
    })


async def get_parallel_verses(
    db,
    language_codes: list[str],
    book_code: str,
    chapter: int,
    verse_start: int | None = None,
    verse_end: int | None = None,
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """
    Fetch the same verses across multiple languages for side-by-side comparison.

    Args:
        db: MongoDBConnector instance
        language_codes: Languages to compare (2-10 unique languages)
        book_code: Book code (e.g., 'genesis', 'john')
        chapter: Chapter number (1-indexed)
        verse_start: Starting verse (default: 1)
        verse_end: Ending verse (default: all in chapter)
        save_to_file: Optional filename to save results (required for >200 verses)

    Returns:
        {
            "parallel_verses": [{book_code, chapter, verse, translations: {lang: {text, translation_type, human_verified?}}}],
            "languages": [str],
            "book_code": str,
            "chapter": int,
            "verse_range": [start, end],
            "count": int,
            "missing_translations": {lang: [verse_nums]}
        }

    Notes:
        - When both human and AI translations exist, human is preferred
        - human_verified field only appears for non-English languages
        - Response includes translation_type so caller knows what they got
    """
    # === Phase 1: Input Validation ===

    # 1. Check for empty input
    if not language_codes:
        return error_response(
            ToolError("invalid_input", "language_codes cannot be empty")
        )

    # 2. Normalize and deduplicate FIRST (case-insensitive)
    language_codes = list(dict.fromkeys(code.lower().strip() for code in language_codes))

    # 3. Validate language count AFTER deduplication
    if len(language_codes) < 2:
        return error_response(
            ToolError("invalid_input", "At least 2 unique languages required for comparison")
        )

    if len(language_codes) > 10:
        return error_response(
            ToolError("invalid_input", "Maximum 10 languages per request")
        )

    # 4. Validate chapter
    if chapter < 1:
        return error_response(
            ToolError("invalid_input", "chapter must be >= 1")
        )

    # 5. Validate verse range
    if verse_start is not None and verse_start < 1:
        return error_response(
            ToolError("invalid_input", "verse_start must be >= 1")
        )

    if verse_start is not None and verse_end is not None and verse_start > verse_end:
        return error_response(
            ToolError("invalid_input", "verse_start cannot exceed verse_end")
        )

    # 6. Validate all languages exist (fail-fast) and store config
    lang_configs = {}
    for code in language_codes:
        try:
            lang_doc = await validate_language(db, code)
            is_base = lang_doc.get("is_base_language", False)
            lang_configs[code] = {
                "is_base": is_base,
                "text_field": "english_text" if is_base else "translated_text",
            }
        except ToolError as e:
            return error_response(e)

    # 7. Validate and normalize book code
    try:
        book_code = validate_book_code(book_code)
    except ToolError as e:
        return error_response(e)

    # === Phase 2: Response Size Protection ===

    MAX_VERSES = 200

    # Estimate verse count - query chapter metadata from bible_books
    # Use the first available language's book for chapter info
    bible_books = db.get_collection("bible_books")
    chapter_verse_count = None

    for code in language_codes:
        book_query = {"language_code": code, "book_code": book_code}
        book_doc = await bible_books.find_one(book_query)
        if book_doc and "chapters" in book_doc:
            for ch in book_doc["chapters"]:
                if ch.get("chapter") == chapter:
                    chapter_verse_count = ch.get("verse_count")
                    break
        if chapter_verse_count is not None:
            break

    # Calculate verse count for request
    if verse_start is not None and verse_end is not None:
        verse_count = verse_end - verse_start + 1
    elif chapter_verse_count is not None:
        if verse_start is not None:
            verse_count = chapter_verse_count - verse_start + 1
        elif verse_end is not None:
            verse_count = verse_end
        else:
            verse_count = chapter_verse_count
    else:
        # Unknown chapter size - allow query but check actual results
        verse_count = None

    if verse_count is not None and verse_count > MAX_VERSES and save_to_file is None:
        return error_response(
            ToolError(
                "response_too_large",
                f"Requested {verse_count} verses exceeds {MAX_VERSES} limit. "
                f"Use save_to_file parameter or specify a smaller verse range.",
                {"verse_count": verse_count, "max_verses": MAX_VERSES},
            )
        )

    # === Phase 3: Query ===

    bible_texts = db.get_collection("bible_texts")

    # Build query (fetch ALL translation types for human > ai priority)
    query = {
        "book_code": book_code,
        "chapter": chapter,
        "language_code": {"$in": language_codes},
    }

    if verse_start is not None:
        query["verse"] = {"$gte": verse_start}
    if verse_end is not None:
        query.setdefault("verse", {})["$lte"] = verse_end

    # Sort by verse ASC, translation_type DESC ("human" > "ai" alphabetically)
    cursor = bible_texts.find(query)
    cursor = cursor.sort([("verse", 1), ("translation_type", -1)])
    docs = await cursor.to_list(length=None)

    # === Phase 4: Group by verse, first-match-wins (human > ai) ===

    verses_by_number = defaultdict(dict)
    all_verse_nums = set()

    for doc in docs:
        verse_num = doc["verse"]
        lang_code = doc["language_code"]
        all_verse_nums.add(verse_num)

        # Skip if we already have a translation for this language+verse
        # (first one wins due to sort order = human preferred)
        if lang_code in verses_by_number[verse_num]:
            continue

        config = lang_configs[lang_code]
        text = doc.get(config["text_field"], "")

        translation_data = {
            "text": text,
            "translation_type": doc.get("translation_type", "human"),
        }

        # Add human_verified only for non-English
        if not config["is_base"]:
            translation_data["human_verified"] = doc.get("human_verified", False)

        verses_by_number[verse_num][lang_code] = translation_data

    # === Phase 5: Build Response ===

    # Sort verse numbers
    sorted_verses = sorted(all_verse_nums)

    # Check actual response size
    if len(sorted_verses) > MAX_VERSES and save_to_file is None:
        return error_response(
            ToolError(
                "response_too_large",
                f"Result contains {len(sorted_verses)} verses, exceeds {MAX_VERSES} limit. "
                f"Use save_to_file parameter or specify a smaller verse range.",
                {"verse_count": len(sorted_verses), "max_verses": MAX_VERSES},
            )
        )

    # Build parallel_verses array
    parallel_verses = []
    for verse_num in sorted_verses:
        parallel_verses.append({
            "book_code": book_code,
            "chapter": chapter,
            "verse": verse_num,
            "translations": verses_by_number[verse_num],
        })

    # Build missing_translations
    missing_translations = {}
    for lang_code in language_codes:
        missing = [v for v in sorted_verses if lang_code not in verses_by_number[v]]
        if missing:
            missing_translations[lang_code] = missing

    # Determine verse range for response
    if sorted_verses:
        actual_start = sorted_verses[0]
        actual_end = sorted_verses[-1]
    else:
        actual_start = verse_start or 1
        actual_end = verse_end or actual_start

    result = {
        "parallel_verses": parallel_verses,
        "languages": language_codes,
        "book_code": book_code,
        "chapter": chapter,
        "verse_range": [actual_start, actual_end],
        "count": len(parallel_verses),
        "missing_translations": missing_translations,
    }

    # === Phase 6: Save to file if requested ===

    if save_to_file is not None:
        try:
            file_result = save_result_to_file(
                result,
                filename=save_to_file,
                prefix=f"parallel_{book_code}_{chapter}",
            )
            return success_response(file_result)
        except ToolError as e:
            return error_response(e)

    return success_response(result)
