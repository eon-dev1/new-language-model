"""
Memories tools for MCP server.

Tools:
- list_language_notes: List all notes for a language
- search_language_notes: Search notes by phrase (case-insensitive)
- list_correction_log: List correction log entries with optional filtering
- search_correction_log: Search correction log entries across multiple fields

Storage patterns:
- language_notes: Embedded array (one doc per language, notes[] inside)
- correction_log: Flat documents (one doc per entry)
"""

import math
import re
from datetime import datetime, timezone
from typing import Any

from constants import Collection
from mcp_server.tools.base import (
    ToolError,
    error_response,
    success_response,
    validate_language,
)

VALID_CONTENT_TYPES = {"bible_verse", "dictionary_entry", "grammar_category"}

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


async def list_language_notes(
    db,
    language_code: str,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List all notes for a language, sorted by updated_at DESC (most recent first).

    Args:
        db: MongoDBConnector instance
        language_code: Language code (normalized before query)
        limit: Max notes to return (default 50, max 100)

    Returns:
        {language_code, notes: [...], count, total}
    """
    # Step 1: Normalize
    language_code = language_code.lower().replace(" ", "_").replace("-", "_")

    # Step 2: Validate
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Clamp limit
    if limit < 1:
        limit = 50
    elif limit > 100:
        limit = 100

    # Step 3: Fetch document
    collection = db.get_collection(Collection.LANGUAGE_NOTES)
    doc = await collection.find_one({"language_code": language_code})

    if doc is None:
        return success_response(
            {"language_code": language_code, "notes": [], "count": 0, "total": 0}
        )

    notes = doc.get("notes", [])
    total = len(notes)

    if not notes:
        return success_response(
            {"language_code": language_code, "notes": [], "count": 0, "total": 0}
        )

    # Step 4: Sort by updated_at DESC (None-safe)
    notes = sorted(notes, key=lambda n: n.get("updated_at") or _EPOCH, reverse=True)

    # Step 5: Paginate
    notes = notes[:limit]

    return success_response(
        {
            "language_code": language_code,
            "notes": notes,
            "count": len(notes),
            "total": total,
        }
    )


async def search_language_notes(
    db,
    language_code: str,
    search_term: str,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Search notes by phrase (case-insensitive substring match on text field).

    Args:
        db: MongoDBConnector instance
        language_code: Language code (normalized before query)
        search_term: Search phrase (empty string returns all notes)
        limit: Max notes to return (default 50, max 100)

    Returns:
        {language_code, search_term, notes: [...], count, total}
    """
    # Step 1: Normalize
    language_code = language_code.lower().replace(" ", "_").replace("-", "_")

    # Step 2: Validate
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Clamp limit
    if limit < 1:
        limit = 50
    elif limit > 100:
        limit = 100

    # Step 3: Fetch document
    collection = db.get_collection(Collection.LANGUAGE_NOTES)
    doc = await collection.find_one({"language_code": language_code})

    if doc is None:
        return success_response(
            {
                "language_code": language_code,
                "search_term": search_term,
                "notes": [],
                "count": 0,
                "total": 0,
            }
        )

    notes = doc.get("notes", [])

    # Step 4: Filter (empty search_term → return all, same as list)
    if search_term:
        search_lower = search_term.lower()
        matches = [n for n in notes if search_lower in n.get("text", "").lower()]
    else:
        matches = list(notes)

    total = len(matches)

    # Step 5: Sort by updated_at DESC (None-safe)
    matches.sort(key=lambda n: n.get("updated_at") or _EPOCH, reverse=True)

    # Step 6: Paginate
    matches = matches[:limit]

    return success_response(
        {
            "language_code": language_code,
            "search_term": search_term,
            "notes": matches,
            "count": len(matches),
            "total": total,
        }
    )


async def list_correction_log(
    db,
    language_code: str,
    content_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    List correction log entries with optional content_type filtering and pagination.

    Args:
        db: MongoDBConnector instance
        language_code: Language code (normalized before query)
        content_type: Optional filter (bible_verse | dictionary_entry | grammar_category)
        page: 1-indexed page number (default 1)
        page_size: Entries per page (default 50, max 100)

    Returns:
        {language_code, content_type, entries: [...], total, page, page_size, total_pages}
    """
    # Step 1: Normalize
    language_code = language_code.lower().replace(" ", "_").replace("-", "_")

    # Step 2: Validate language
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate content_type
    if content_type is not None and content_type not in VALID_CONTENT_TYPES:
        return error_response(
            ToolError(
                "invalid_input",
                f"Invalid content_type '{content_type}'. Must be one of: bible_verse, dictionary_entry, grammar_category",
                {"content_type": content_type},
            )
        )

    # Validate page
    if page < 1:
        return error_response(
            ToolError(
                "invalid_input",
                f"page must be >= 1, got {page}",
                {"page": page},
            )
        )

    # Clamp page_size
    if page_size < 1:
        page_size = 50
    elif page_size > 100:
        page_size = 100

    # Step 3: Build query
    query: dict[str, Any] = {"language_code": language_code}
    if content_type is not None:
        query["content_type"] = content_type

    # Step 4: Count total matching documents
    collection = db.get_collection(Collection.CORRECTION_LOG)
    total = await collection.count_documents(query)

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Step 5: Fetch paginated entries, sorted by created_at DESC, _id DESC
    skip = (page - 1) * page_size
    entries_cursor = (
        collection.find(query)
        .sort([("created_at", -1), ("_id", -1)])
        .skip(skip)
        .limit(page_size)
    )
    entries = await entries_cursor.to_list(None)

    # Serialize _id to string
    for entry in entries:
        if "_id" in entry:
            entry["id"] = str(entry.pop("_id"))

    return success_response(
        {
            "language_code": language_code,
            "content_type": content_type,
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    )


async def search_correction_log(
    db,
    language_code: str,
    search_term: str,
    content_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Search correction log entries across original_text, what_was_wrong, correction fields.

    Uses MongoDB $regex with re.escape() to prevent metacharacter injection.

    Args:
        db: MongoDBConnector instance
        language_code: Language code (normalized before query)
        search_term: Search phrase (empty string returns all corrections)
        content_type: Optional filter (bible_verse | dictionary_entry | grammar_category)
        limit: Max entries to return (default 50, max 100)

    Returns:
        {language_code, search_term, content_type, entries: [...], count, total}
    """
    # Step 1: Normalize
    language_code = language_code.lower().replace(" ", "_").replace("-", "_")

    # Step 2: Validate language
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate content_type
    if content_type is not None and content_type not in VALID_CONTENT_TYPES:
        return error_response(
            ToolError(
                "invalid_input",
                f"Invalid content_type '{content_type}'. Must be one of: bible_verse, dictionary_entry, grammar_category",
                {"content_type": content_type},
            )
        )

    # Clamp limit
    if limit < 1:
        limit = 50
    elif limit > 100:
        limit = 100

    # Step 3: Build base query
    query: dict[str, Any] = {"language_code": language_code}
    if content_type is not None:
        query["content_type"] = content_type

    # Step 4: Add $or text search (re.escape prevents regex metacharacter injection)
    if search_term:
        escaped_search = re.escape(search_term)
        query["$or"] = [
            {"original_text": {"$regex": escaped_search, "$options": "i"}},
            {"what_was_wrong": {"$regex": escaped_search, "$options": "i"}},
            {"correction": {"$regex": escaped_search, "$options": "i"}},
        ]

    # Step 5: Count total matching documents
    collection = db.get_collection(Collection.CORRECTION_LOG)
    total = await collection.count_documents(query)

    # Step 6: Fetch entries sorted by created_at DESC
    entries_cursor = (
        collection.find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    entries = await entries_cursor.to_list(None)

    # Serialize _id to string
    for entry in entries:
        if "_id" in entry:
            entry["id"] = str(entry.pop("_id"))

    return success_response(
        {
            "language_code": language_code,
            "search_term": search_term,
            "content_type": content_type,
            "entries": entries,
            "count": len(entries),
            "total": total,
        }
    )
