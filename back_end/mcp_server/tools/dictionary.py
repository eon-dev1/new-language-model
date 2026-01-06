"""
Dictionary tools for MCP server.

Tools:
- list_dictionary_entries: Paginated list of entries from embedded array
- get_dictionary_entry: Get specific word entry
- upsert_dictionary_entries: Insert/update entries with O(n+m) optimization

Note: Dictionary uses embedded entries[] array pattern.
One doc per (language, translation_type) with entries embedded.
"""

from datetime import datetime, timezone
from typing import Any

from mcp_server.tools.base import (
    ToolError,
    error_response,
    success_response,
    validate_language,
    validate_translation_type,
)


async def _get_dictionary_doc(
    db, language_code: str, translation_type: str | None = None
) -> dict | None:
    """
    Get dictionary document for a language.

    Args:
        db: MongoDBConnector instance
        language_code: Language code
        translation_type: Optional filter

    Returns:
        Dictionary document or None
    """
    dictionaries = db.get_collection("dictionaries")

    query = {"language_code": language_code.lower()}
    if translation_type:
        query["translation_type"] = translation_type

    return await dictionaries.find_one(query)


async def list_dictionary_entries(
    db,
    language_code: str,
    translation_type: str | None = None,
    offset: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated dictionary entries.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get entries for
        translation_type: Optional filter ("human" or "ai")
        offset: Number of entries to skip
        limit: Maximum entries to return
        search: Optional search term (searches word and definition)

    Returns:
        {
            "entries": [{word, definition, part_of_speech, ...}],
            "total": int,
            "offset": int,
            "limit": int
        }
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate translation type
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # Get dictionary document
    doc = await _get_dictionary_doc(db, language_code, translation_type)

    if doc is None:
        return success_response(
            {"entries": [], "total": 0, "offset": offset, "limit": limit}
        )

    entries = doc.get("entries", [])

    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        entries = [
            e
            for e in entries
            if search_lower in e.get("word", "").lower()
            or search_lower in e.get("definition", "").lower()
        ]

    total = len(entries)

    # Apply pagination
    entries = entries[offset : offset + limit]

    return success_response(
        {"entries": entries, "total": total, "offset": offset, "limit": limit}
    )


async def get_dictionary_entry(
    db,
    language_code: str,
    word: str,
    translation_type: str | None = None,
) -> dict[str, Any]:
    """
    Get a specific dictionary entry by word.

    Args:
        db: MongoDBConnector instance
        language_code: Language to search
        word: Word to find
        translation_type: Optional filter ("human" or "ai")

    Returns:
        Entry document or error
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate translation type
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # Get dictionary document
    doc = await _get_dictionary_doc(db, language_code, translation_type)

    if doc is None:
        return error_response(
            ToolError(
                "not_found",
                f"No dictionary found for language '{language_code}'",
                {"language_code": language_code},
            )
        )

    # Search for word in entries
    entries = doc.get("entries", [])
    for entry in entries:
        if entry.get("word") == word:
            return entry

    return error_response(
        ToolError(
            "not_found",
            f"Word '{word}' not found in dictionary",
            {"language_code": language_code, "word": word},
        )
    )


async def upsert_dictionary_entries(
    db,
    language_code: str,
    translation_type: str | None,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Insert or update dictionary entries.

    Uses O(n+m) optimization: builds word→index lookup first.

    Args:
        db: MongoDBConnector instance
        language_code: Target language
        translation_type: Required ("human" or "ai")
        entries: List of entry dicts with word, definition, part_of_speech

    Returns:
        {"created": int, "updated": int, "total": int}
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # translation_type is required for writes
    if translation_type is None:
        return error_response(
            ToolError(
                "invalid_input",
                "translation_type is required for write operations",
                {"translation_type": None},
            )
        )

    # Validate translation type
    try:
        validate_translation_type(translation_type)
    except ToolError as e:
        return error_response(e)

    # Handle empty entries
    if not entries:
        return success_response({"created": 0, "updated": 0, "total": 0})

    # Validate each entry has required fields
    for entry in entries:
        if "word" not in entry:
            return error_response(
                ToolError(
                    "validation_error",
                    "Entry missing required field 'word'",
                    {"entry": entry},
                )
            )
        if "definition" not in entry:
            return error_response(
                ToolError(
                    "validation_error",
                    "Entry missing required field 'definition'",
                    {"entry": entry},
                )
            )

    dictionaries = db.get_collection("dictionaries")

    # Get existing dictionary document
    doc = await _get_dictionary_doc(db, language_code, translation_type)

    if doc is None:
        # Create new dictionary document with entries
        now = datetime.now(timezone.utc)
        for entry in entries:
            entry["created_at"] = now
            entry["updated_at"] = now

        new_doc = {
            "language_code": language_code.lower(),
            "translation_type": translation_type,
            "entries": entries,
            "entry_count": len(entries),
            "created_at": now,
        }
        await dictionaries.insert_one(new_doc)

        return success_response(
            {"created": len(entries), "updated": 0, "total": len(entries)}
        )

    # Build word→index lookup for O(n+m) performance
    existing_entries = doc.get("entries", [])
    word_to_index = {e["word"]: i for i, e in enumerate(existing_entries)}

    created = 0
    updated = 0
    now = datetime.now(timezone.utc)

    for entry in entries:
        word = entry["word"]
        entry["updated_at"] = now

        if word in word_to_index:
            # Update existing entry
            idx = word_to_index[word]
            await dictionaries.update_one(
                {"_id": doc["_id"]},
                {"$set": {f"entries.{idx}": {**existing_entries[idx], **entry}}},
            )
            updated += 1
        else:
            # Insert new entry
            entry["created_at"] = now
            await dictionaries.update_one(
                {"_id": doc["_id"]},
                {"$push": {"entries": entry}, "$inc": {"entry_count": 1}},
            )
            # Add to lookup for subsequent entries
            word_to_index[word] = len(existing_entries) + created
            created += 1

    total = len(existing_entries) + created

    return success_response({"created": created, "updated": updated, "total": total})
