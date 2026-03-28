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
from typing import List, Optional
from datetime import datetime
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
                "created_at": datetime.utcnow(),
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

        now = datetime.utcnow()
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
                    f"entries.{entry_index}.updated_at": datetime.utcnow()
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
