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

logger = logging.getLogger(__name__)


def _entry_debug_summary(entry: dict[str, Any]) -> str:
    """
    Compact, log-safe description of an inbound entry.

    Logs the key names verbatim (that's what diagnoses schema mismatches, e.g. a model
    sending human_verified) but only the length of free-text values, so a large
    definition can't flood the log.
    """
    word = str(entry.get("word", "<no word>"))[:60]
    definition_len = len(str(entry.get("definition", "")))
    return f"word={word!r} keys={sorted(entry.keys())} definition_len={definition_len}"


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
    logger.info(
        f"upsert_dictionary_entries CALLED language={language_code!r} "
        f"entry_count={len(entries) if entries else 0}"
    )
    for i, entry in enumerate(entries or []):
        logger.info(f"  inbound entry[{i}]: {_entry_debug_summary(entry)}")

    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        logger.warning(
            f"upsert REJECTED at language validation: language={language_code!r} code={e.code}"
        )
        return error_response(e)

    # Handle empty entries
    if not entries:
        logger.info("upsert short-circuit: empty entries list, nothing written")
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
            # original_word is a REST-only disambiguation signal, never persisted here.
            dumped = validated.model_dump(exclude_unset=True, exclude={"original_word"})
            # Forced True to match routes/dictionary.py's REST endpoint, which also
            # hardcodes human_verified=True on save. This covers the in-app chat path:
            # tool_registry.py registers this tool readonly=False, so routes/chat.py's
            # call_tool() always shows the approval card before invoking it. It does NOT
            # cover mcp_server/server.py's FastMCP entrypoint (used when this repo's
            # .mcp.json wires nlm-database into Claude Code/Desktop directly) — that path
            # never touches tool_registry.py, so review there depends entirely on the
            # calling MCP client's own tool-approval settings, not on anything enforced
            # in this codebase. Revisit if that path needs its own explicit gate.
            dumped["human_verified"] = True
            validated_entries.append(dumped)
        except ValidationError as e:
            # The single most common real-world failure: a model sends an extra key
            # (CreateEntryRequest is extra="forbid"), so log exactly which fields
            # Pydantic objected to rather than only that "validation failed".
            rejected_fields = [
                ".".join(str(p) for p in err.get("loc", ())) for err in e.errors()
            ]
            logger.warning(
                f"upsert REJECTED at pydantic validation: {_entry_debug_summary(entry)} "
                f"rejected_fields={rejected_fields} error_types="
                f"{[err.get('type') for err in e.errors()]}"
            )
            return error_response(
                ToolError(
                    "validation_error",
                    str(e),
                    {"entry": entry},
                )
            )
    entries = validated_entries
    logger.info(f"upsert validation passed for {len(entries)} entries")

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
        logger.info(
            f"upsert branch=NEW_DOC: no existing dictionary for {language_code!r}, "
            f"inserting doc with {len(entries)} entries"
        )
        insert_result = await dictionaries.insert_one(new_doc)
        logger.info(f"upsert NEW_DOC insert_one inserted_id={insert_result.inserted_id!r}")

        await _sync_word_index_flags(db, language_code, entries)
        logger.info(
            f"upsert DONE (new doc) language={language_code!r} "
            f"created={len(entries)} updated=0 total={len(entries)}"
        )
        return success_response(
            {"created": len(entries), "updated": 0, "total": len(entries)}
        )

    # Build word→index lookup for O(n+m) performance
    existing_entries = doc.get("entries", [])
    word_to_index = {e["word"]: i for i, e in enumerate(existing_entries)}
    # Local mirror of what's actually at each index in the document, kept in sync as we
    # go. Needed because a batch can repeat a word (e.g. an LLM correcting the same
    # entry twice in one call): the second occurrence must merge against what the first
    # occurrence just wrote, not against the pre-loop `existing_entries` snapshot, which
    # doesn't have an entry at a not-yet-pushed index and would raise IndexError.
    known_entries = list(existing_entries)

    created = 0
    updated = 0
    now = datetime.now(timezone.utc)

    logger.info(
        f"upsert branch=EXISTING_DOC _id={doc['_id']!r} "
        f"existing_entry_count={len(existing_entries)} "
        f"stored_entry_count_field={doc.get('entry_count')!r}"
    )

    for entry in entries:
        word = entry["word"]
        entry["updated_at"] = now

        if word in word_to_index:
            # Update existing entry
            idx = word_to_index[word]
            merged = {**known_entries[idx], **entry}
            result = await dictionaries.update_one(
                {"_id": doc["_id"]},
                {"$set": {f"entries.{idx}": merged}},
            )
            # matched/modified are otherwise discarded here. A modified_count of 0 is
            # the signature of a write that silently did nothing (doc vanished, or the
            # $set was a no-op), which the return value alone would still report as a
            # successful "updated".
            logger.info(
                f"upsert $SET word={word!r} idx={idx} "
                f"matched={result.matched_count} modified={result.modified_count} "
                f"human_verified={merged.get('human_verified')!r}"
            )
            known_entries[idx] = merged
            updated += 1
        else:
            # Insert new entry
            entry["created_at"] = now
            result = await dictionaries.update_one(
                {"_id": doc["_id"]},
                {"$push": {"entries": entry}, "$inc": {"entry_count": 1}},
            )
            logger.info(
                f"upsert $PUSH word={word!r} "
                f"matched={result.matched_count} modified={result.modified_count} "
                f"human_verified={entry.get('human_verified')!r}"
            )
            # Add to lookup for subsequent entries
            word_to_index[word] = len(known_entries)
            known_entries.append(entry)
            created += 1

    total = len(existing_entries) + created

    await _sync_word_index_flags(db, language_code, entries)
    logger.info(
        f"upsert DONE language={language_code!r} "
        f"created={created} updated={updated} total={total}"
    )
    return success_response({"created": created, "updated": updated, "total": total})


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
