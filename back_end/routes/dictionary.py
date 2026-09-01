# dictionary.py
"""
Dictionary endpoints for language dictionary views.

Provides endpoints to:
- Fetch dictionary entries for a language
- Create/update dictionary entries
- Update human_verified status for entries
"""

from fastapi import APIRouter, HTTPException, Path, Body, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated, List, Optional
from datetime import datetime, timezone
import logging

from db_connector.connection import MongoDBConnector
from constants import Collection
from utils.word_index.builder import sync_dictionary_flags
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Helper Functions ---

def _normalize_examples(examples_value) -> List[str]:
    """
    Normalize examples field to always return a list.

    Handles legacy data where examples might be stored as:
    - string: "example1, example2" → ["example1, example2"]
    - list: ["ex1", "ex2"] → ["ex1", "ex2"]
    - None/missing → []
    """
    if examples_value is None:
        return []
    if isinstance(examples_value, str):
        # Legacy data: examples stored as string instead of list
        return [examples_value] if examples_value else []
    if isinstance(examples_value, list):
        return examples_value
    # Fallback for unexpected types
    return []


# --- Pydantic Models ---

class DictionaryEntry(BaseModel):
    """Single dictionary entry."""
    word: str
    definition: str = ""
    part_of_speech: Optional[str] = None
    examples: List[str] = []
    human_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EntriesResponse(BaseModel):
    """Response containing dictionary entries."""
    language_code: str
    entries: List[DictionaryEntry]
    count: int


class CreateEntryRequest(BaseModel):
    """Request to create or update a dictionary entry."""
    model_config = ConfigDict(extra="forbid")

    word: str = Field(..., min_length=1, max_length=200)
    definition: str = Field(..., min_length=1, max_length=5000)
    part_of_speech: Optional[str] = None
    examples: List[str] = []
    # REST-only disambiguation signal: the word this form was opened with (or None if
    # opened blank). Lets the backend tell "renaming/creating" apart from "same-word edit"
    # without a separate immutable entry ID. Compared, never persisted (see mcp_server
    # exclusion below).
    original_word: Optional[str] = None


class CreateEntryResponse(BaseModel):
    """Response confirming entry creation/update."""
    success: bool
    word: str
    language_code: str
    action: str  # "created" or "updated"


class VerifyEntryRequest(BaseModel):
    """Request to update entry verification status."""
    human_verified: bool


class VerifyEntryResponse(BaseModel):
    """Response confirming verification update."""
    success: bool
    word: str
    language_code: str
    human_verified: bool


class DeleteEntriesRequest(BaseModel):
    """Request to delete one or more dictionary entries by word."""
    model_config = ConfigDict(extra="forbid")

    words: List[Annotated[str, Field(max_length=200)]] = Field(..., min_length=1)


class DeleteEntriesResponse(BaseModel):
    """Response confirming the requested words are no longer in the dictionary."""
    success: bool
    language_code: str
    absent: List[str]


# --- Endpoints ---

@router.get("/dictionary/{language}/entries", response_model=EntriesResponse)
async def get_dictionary_entries(
    language: str = Path(..., description="Language code (e.g., 'kope', 'french')"),
    db: MongoDBConnector = Depends(get_db)
) -> EntriesResponse:
    """
    Fetch all dictionary entries for a language.

    Returns entries sorted alphabetically by word.

    Args:
        language: Target language code

    Returns:
        EntriesResponse with entries

    Raises:
        HTTPException: 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        # Fetch the single dictionary document for this language
        doc = await dictionaries.find_one({"language_code": language_code})

        if not doc:
            # Return empty response instead of 404 - allows UI to show "create first entry"
            logger.info(f"No dictionary found for {language_code}, returning empty response")
            return EntriesResponse(language_code=language_code, entries=[], count=0)

        # Build flat entries list
        entries = []
        for entry in doc.get("entries", []):
            word = entry.get("word", "").lower()
            if word:
                entries.append(DictionaryEntry(
                    word=word,
                    definition=entry.get("definition", ""),
                    part_of_speech=entry.get("part_of_speech"),
                    examples=_normalize_examples(entry.get("examples")),
                    human_verified=entry.get("human_verified", False),
                    created_at=entry.get("created_at"),
                    updated_at=entry.get("updated_at")
                ))

        # Sort alphabetically
        entries.sort(key=lambda e: e.word)

        logger.info(f"Retrieved {len(entries)} dictionary entries for {language_code}")

        return EntriesResponse(
            language_code=language_code,
            entries=entries,
            count=len(entries)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Fetch dictionary entries for {language}", e)


@router.post("/dictionary/{language}/entries", response_model=CreateEntryResponse)
async def create_or_update_entry(
    language: str = Path(..., description="Language code"),
    request: CreateEntryRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> CreateEntryResponse:
    """
    Create or update a dictionary entry.

    If the word already exists, updates it. Otherwise, creates a new entry.
    Auto-sets human_verified = true.

    Args:
        language: Target language code
        request: Entry data (word, definition, part_of_speech, examples)

    Returns:
        CreateEntryResponse confirming creation/update

    Raises:
        HTTPException: 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        word_normalized = request.word.strip().lower()

        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        # Get the dictionary document
        doc = await dictionaries.find_one({"language_code": language_code})

        if not doc:
            # Create new dictionary document (upsert pattern)
            logger.info(f"Creating new dictionary for {language_code}")
            new_doc = {
                "language_code": language_code,
                "language_name": language_code.replace('_', ' ').title(),
                "dictionary_name": f"{language_code.replace('_', ' ').title()} Dictionary",
                "entries": [],
                "entry_count": 0,
                "created_at": datetime.now(timezone.utc),
                "categories": ["noun", "verb", "adjective", "adverb", "other"],
                "metadata": {
                    "description": f"Dictionary for {language_code}",
                    "version": "1.0",
                    "status": "active",
                }
            }
            await dictionaries.insert_one(new_doc)
            doc = new_doc

        # Check if word already exists
        existing_entries = doc.get("entries", [])
        existing_index = next(
            (i for i, e in enumerate(existing_entries) if e.get("word", "").lower() == word_normalized),
            None
        )

        # original_word disambiguates "changing which word this entry occupies"
        # (create/rename) from "updating the same word" (ordinary edit). original_index
        # is computed unconditionally — a real word can never equal None, so it naturally
        # comes out None when original_word wasn't sent, with no separate branch needed.
        original_normalized = (
            request.original_word.strip().lower() if request.original_word is not None else None
        )
        original_index = next(
            (i for i, e in enumerate(existing_entries) if e.get("word", "").lower() == original_normalized),
            None
        )

        if existing_index is not None and existing_index != original_index:
            # This save would make two distinct logical entries share a normalized word.
            # Reject before any write; nothing in entries[]/entry_count changes.
            conflicting_entry = existing_entries[existing_index]
            existing_pos = conflicting_entry.get("part_of_speech") or None
            existing_def = conflicting_entry.get("definition", "") or ""
            existing_def_preview = existing_def[:200] + "…" if len(existing_def) > 200 else existing_def
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "word_conflict",
                    "word": word_normalized,
                    "message": f"An entry for '{word_normalized}' already exists.",
                    "existing_preview": {
                        "part_of_speech": existing_pos,
                        "definition": existing_def_preview,
                    },
                },
            )

        now = datetime.now(timezone.utc)
        new_entry = {
            "word": word_normalized,
            "definition": request.definition,
            "part_of_speech": request.part_of_speech,
            "examples": request.examples,
            "human_verified": True,  # Auto-verified on human save
            "updated_at": now
        }

        if existing_index is not None:
            # Update existing entry
            new_entry["created_at"] = existing_entries[existing_index].get("created_at", now)
            result = await dictionaries.update_one(
                {"language_code": language_code},
                {"$set": {f"entries.{existing_index}": new_entry}}
            )
            action = "updated"
        else:
            # Create new entry
            new_entry["created_at"] = now
            result = await dictionaries.update_one(
                {"language_code": language_code},
                {
                    "$push": {"entries": new_entry},
                    "$inc": {"entry_count": 1}
                }
            )
            action = "created"

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to {action} entry"
            )

        logger.info(f"{action.capitalize()} dictionary entry '{word_normalized}' for {language_code}")

        # Update in_dictionary flags in word index (targeted, not full rebuild)
        try:
            await sync_dictionary_flags(db, language_code, words=[word_normalized])
        except Exception as e:
            logger.warning(f"Word index dictionary sync failed (non-fatal): {e}")

        return CreateEntryResponse(
            success=True,
            word=word_normalized,
            language_code=language_code,
            action=action
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Create/update dictionary entry for {language}", e)


@router.patch("/dictionary/{language}/entries/{word}/verify", response_model=VerifyEntryResponse)
async def verify_dictionary_entry(
    language: str = Path(..., description="Language code"),
    word: str = Path(..., description="Word to verify"),
    request: VerifyEntryRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> VerifyEntryResponse:
    """
    Update human_verified status for a dictionary entry.

    Args:
        language: Target language code
        word: The word to verify
        request: Contains human_verified status

    Returns:
        VerifyEntryResponse confirming the update

    Raises:
        HTTPException: 404 if entry not found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        word_normalized = word.strip().lower()

        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        # Get the dictionary document
        doc = await dictionaries.find_one({"language_code": language_code})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Dictionary not found for {language}"
            )

        # Find entry index
        entries = doc.get("entries", [])
        entry_index = next(
            (i for i, e in enumerate(entries) if e.get("word", "").lower() == word_normalized),
            None
        )

        if entry_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Entry '{word}' not found in dictionary"
            )

        # Update verification status
        result = await dictionaries.update_one(
            {"language_code": language_code},
            {
                "$set": {
                    f"entries.{entry_index}.human_verified": request.human_verified,
                    f"entries.{entry_index}.updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update verification status"
            )

        logger.info(
            f"Updated verification for '{word_normalized}' in "
            f"dictionary for {language_code}: {request.human_verified}"
        )

        return VerifyEntryResponse(
            success=True,
            word=word_normalized,
            language_code=language_code,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify dictionary entry {word} for {language}", e)


@router.post("/dictionary/{language}/entries/delete", response_model=DeleteEntriesResponse)
async def delete_dictionary_entries(
    language: str = Path(..., description="Language code"),
    request: DeleteEntriesRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> DeleteEntriesResponse:
    """
    Delete one or more dictionary entries by word (hard delete, no undo).

    Words are normalized (.strip().lower()) before matching. Matching is
    case-insensitive against the stored word regardless of how it was stored.
    A requested word not currently in the dictionary is treated the same as
    one just removed: both come back in `absent`, no error either way.
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        doc = await dictionaries.find_one({"language_code": language_code})
        if not doc:
            raise HTTPException(status_code=404, detail=f"Dictionary not found for {language}")

        existing_entries = doc.get("entries", [])
        existing_words = {
            e["word"].strip().lower()
            for e in existing_entries
            if isinstance(e.get("word"), str) and e["word"].strip()
        }
        normalized_requested = sorted({w.strip().lower() for w in request.words})

        deleted = [w for w in normalized_requested if w in existing_words]

        if deleted:
            await dictionaries.update_one(
                {"language_code": language_code},
                [
                    {
                        "$set": {
                            "entries": {
                                "$filter": {
                                    "input": "$entries",
                                    "cond": {
                                        "$not": [
                                            {
                                                "$in": [
                                                    {
                                                        "$toLower": {
                                                            "$trim": {
                                                                "input": {
                                                                    "$cond": [
                                                                        {"$eq": [{"$type": "$$this.word"}, "string"]},
                                                                        "$$this.word",
                                                                        ""
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    },
                                                    deleted
                                                ]
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    {"$set": {"entry_count": {"$size": "$entries"}}}
                ]
            )

            try:
                await sync_dictionary_flags(db, language_code, words=deleted)
            except Exception as e:
                logger.warning(f"Word index dictionary sync failed (non-fatal): {e}")

        logger.info(f"Deleted {len(deleted)} dictionary entries for {language_code}: {deleted}")

        return DeleteEntriesResponse(
            success=True,
            language_code=language_code,
            absent=normalized_requested
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Delete dictionary entries for {language}", e)
