"""
Dictionary tools for MCP server.

Tools:
- list_dictionary_entries: Paginated list of entries from embedded array
- get_dictionary_entry: Get specific word entry
- upsert_dictionary_entries: Insert/update entries with O(n+m) optimization

Note: Dictionary uses embedded entries[] array pattern.
One doc per language with entries embedded.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from constants import Collection
from mcp_server.tools.base import (
    ToolError,
    error_response,
    success_response,
    validate_language,
)
from routes.dictionary import CreateEntryRequest


async def _get_dictionary_doc(db, language_code: str) -> dict | None:
    """
    Get dictionary document for a language.

    Args:
        db: MongoDBConnector instance
        language_code: Language code

    Returns:
        Dictionary document or None
    """
    dictionaries = db.get_collection("dictionaries")
    return await dictionaries.find_one({"language_code": language_code.lower()})


async def list_dictionary_entries(
    db,
    language_code: str,
    offset: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated dictionary entries.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get entries for
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

    # Get dictionary document
    doc = await _get_dictionary_doc(db, language_code)

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
) -> dict[str, Any]:
    """
    Get a specific dictionary entry by word.

    Args:
        db: MongoDBConnector instance
        language_code: Language to search
        word: Word to find

    Returns:
        Entry document or error
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Get dictionary document
    doc = await _get_dictionary_doc(db, language_code)

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
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Insert or update dictionary entries.

    Uses O(n+m) optimization: builds word→index lookup first.

    Args:
        db: MongoDBConnector instance
        language_code: Target language
        entries: List of entry dicts with word, definition, part_of_speech

    Returns:
        {"created": int, "updated": int, "total": int}
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
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

    # Validate and sanitize each entry via the shared Pydantic model
    validated_entries = []
    for entry in entries:
        try:
            validated = CreateEntryRequest.model_validate(entry)
            validated_entries.append(validated.model_dump(exclude_unset=True))
        except ValidationError as e:
            return error_response(
                ToolError(
                    "validation_error",
                    str(e),
                    {"entry": entry},
                )
            )
    entries = validated_entries

    dictionaries = db.get_collection("dictionaries")

    # Get existing dictionary document
    doc = await _get_dictionary_doc(db, language_code)

    if doc is None:
        # Create new dictionary document with entries
        now = datetime.now(timezone.utc)
        for entry in entries:
            entry["created_at"] = now
            entry["updated_at"] = now

        new_doc = {
            "language_code": language_code.lower(),
            "entries": entries,
            "entry_count": len(entries),
            "created_at": now,
        }
        await dictionaries.insert_one(new_doc)

        await _sync_word_index_flags(db, language_code, entries)
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

    await _sync_word_index_flags(db, language_code, entries)
    return success_response({"created": created, "updated": updated, "total": total})


logger = logging.getLogger(__name__)


async def _sync_word_index_flags(
    db, language_code: str, entries: list[dict[str, Any]]
) -> None:
    """Update word index in_dictionary flags after dictionary entries are saved."""
    try:
        word_index_col = db.get_collection(Collection.WORD_INDEX)
        new_words = [e["word"].lower() for e in entries if "word" in e]
        if new_words:
            await word_index_col.update_many(
                {"language_code": language_code.lower(), "word": {"$in": new_words}},
                {"$set": {"in_dictionary": True}},
            )
    except Exception as e:
        logger.warning(f"Word index dictionary sync failed (non-fatal): {e}")
