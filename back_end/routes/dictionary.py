# dictionary.py
"""
Dictionary endpoints for unified human/AI dictionary views.

Provides endpoints to:
- Fetch merged dictionary entries from both human and AI sources
- Create/update human dictionary entries
- Update human_verified status for entries
"""

from fastapi import APIRouter, HTTPException, Path, Body, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging

from db_connector.connection import MongoDBConnector
from constants import Collection, TranslationType
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Pydantic Models ---

class EntryVersion(BaseModel):
    """Single version (human or AI) of a dictionary entry."""
    definition: str
    part_of_speech: Optional[str] = None
    examples: List[str] = []
    human_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MergedEntry(BaseModel):
    """Dictionary entry with optional human and AI versions."""
    word: str
    human: Optional[EntryVersion] = None
    ai: Optional[EntryVersion] = None


class EntriesResponse(BaseModel):
    """Response containing merged dictionary entries."""
    language_code: str
    entries: List[MergedEntry]
    count: int


class CreateEntryRequest(BaseModel):
    """Request to create or update a human dictionary entry."""
    word: str = Field(..., min_length=1)
    definition: str = Field(..., min_length=1)
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
    translation_type: str = Field(..., pattern="^(human|ai)$")
    human_verified: bool


class VerifyEntryResponse(BaseModel):
    """Response confirming verification update."""
    success: bool
    word: str
    language_code: str
    translation_type: str
    human_verified: bool


# --- Endpoints ---

@router.get("/dictionary/{language}/entries", response_model=EntriesResponse)
async def get_dictionary_entries(
    language: str = Path(..., description="Language code (e.g., 'kope', 'french')"),
    db: MongoDBConnector = Depends(get_db)
) -> EntriesResponse:
    """
    Fetch all dictionary entries for a language, merging human and AI versions.

    Returns entries with both human and AI versions where available,
    sorted alphabetically by word.

    Args:
        language: Target language code

    Returns:
        EntriesResponse with merged entries from both sources

    Raises:
        HTTPException: 404 if no dictionary found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        # Fetch both human and AI dictionary documents
        human_doc = await dictionaries.find_one({
            "language_code": language_code,
            "translation_type": TranslationType.HUMAN
        })
        ai_doc = await dictionaries.find_one({
            "language_code": language_code,
            "translation_type": TranslationType.AI
        })

        if not human_doc and not ai_doc:
            # Return empty response instead of 404 - allows UI to show "create first entry"
            logger.info(f"No dictionary found for {language_code}, returning empty response")
            return EntriesResponse(language_code=language_code, entries=[], count=0)

        # Build word -> versions map
        entries_map: dict = {}

        # Process human entries
        if human_doc and human_doc.get("entries"):
            for entry in human_doc["entries"]:
                word = entry.get("word", "").lower()
                if word:
                    if word not in entries_map:
                        entries_map[word] = {"word": word}
                    entries_map[word]["human"] = EntryVersion(
                        definition=entry.get("definition", ""),
                        part_of_speech=entry.get("part_of_speech"),
                        examples=entry.get("examples", []),
                        human_verified=entry.get("human_verified", False),
                        created_at=entry.get("created_at"),
                        updated_at=entry.get("updated_at")
                    )

        # Process AI entries
        if ai_doc and ai_doc.get("entries"):
            for entry in ai_doc["entries"]:
                word = entry.get("word", "").lower()
                if word:
                    if word not in entries_map:
                        entries_map[word] = {"word": word}
                    entries_map[word]["ai"] = EntryVersion(
                        definition=entry.get("definition", ""),
                        part_of_speech=entry.get("part_of_speech"),
                        examples=entry.get("examples", []),
                        human_verified=entry.get("human_verified", False),
                        created_at=entry.get("created_at"),
                        updated_at=entry.get("updated_at")
                    )

        # Convert to list and sort alphabetically
        merged_entries = [
            MergedEntry(
                word=data["word"],
                human=data.get("human"),
                ai=data.get("ai")
            )
            for data in sorted(entries_map.values(), key=lambda x: x["word"])
        ]

        logger.info(f"Retrieved {len(merged_entries)} dictionary entries for {language_code}")

        return EntriesResponse(
            language_code=language_code,
            entries=merged_entries,
            count=len(merged_entries)
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
    Create or update a human dictionary entry.

    If the word already exists in the human dictionary, updates it.
    Otherwise, creates a new entry. Auto-sets human_verified = true.

    This endpoint is used when:
    - Creating new human entries from scratch
    - Editing AI entries (creates new human doc, preserves AI)

    Args:
        language: Target language code
        request: Entry data (word, definition, part_of_speech, examples)

    Returns:
        CreateEntryResponse confirming creation/update

    Raises:
        HTTPException: 404 if dictionary not found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        word_normalized = request.word.strip().lower()

        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        # Get the human dictionary document
        human_doc = await dictionaries.find_one({
            "language_code": language_code,
            "translation_type": TranslationType.HUMAN
        })

        if not human_doc:
            # Create new dictionary document (upsert pattern)
            logger.info(f"Creating new human dictionary for {language_code}")
            new_doc = {
                "language_code": language_code,
                "language_name": language_code.replace('_', ' ').title(),
                "translation_type": TranslationType.HUMAN,
                "dictionary_name": f"{language_code.replace('_', ' ').title()} Human Dictionary",
                "entries": [],
                "entry_count": 0,
                "created_at": datetime.utcnow(),
                "categories": ["noun", "verb", "adjective", "adverb", "other"],
                "metadata": {
                    "description": f"Human-curated dictionary for {language_code}",
                    "version": "1.0",
                    "status": "active",
                    "generation_method": "human"
                }
            }
            await dictionaries.insert_one(new_doc)
            human_doc = new_doc

        # Check if word already exists
        existing_entries = human_doc.get("entries", [])
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
                {
                    "language_code": language_code,
                    "translation_type": TranslationType.HUMAN
                },
                {
                    "$set": {f"entries.{existing_index}": new_entry}
                }
            )
            action = "updated"
        else:
            # Create new entry
            new_entry["created_at"] = now
            result = await dictionaries.update_one(
                {
                    "language_code": language_code,
                    "translation_type": TranslationType.HUMAN
                },
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

    Can verify either human or AI entries based on translation_type.
    Used for Scenario 2: AI is correct, just verify without editing.

    Args:
        language: Target language code
        word: The word to verify
        request: Contains translation_type and human_verified status

    Returns:
        VerifyEntryResponse confirming the update

    Raises:
        HTTPException: 404 if entry not found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        word_normalized = word.strip().lower()
        translation_type = request.translation_type

        database = db.get_database()
        dictionaries = database[Collection.DICTIONARIES]

        # Get the specified dictionary document
        doc = await dictionaries.find_one({
            "language_code": language_code,
            "translation_type": translation_type
        })

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"{translation_type.capitalize()} dictionary not found for {language}"
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
                detail=f"Entry '{word}' not found in {translation_type} dictionary"
            )

        # Update verification status
        result = await dictionaries.update_one(
            {
                "language_code": language_code,
                "translation_type": translation_type
            },
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
            f"Updated verification for '{word_normalized}' in {translation_type} "
            f"dictionary for {language_code}: {request.human_verified}"
        )

        return VerifyEntryResponse(
            success=True,
            word=word_normalized,
            language_code=language_code,
            translation_type=translation_type,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify dictionary entry {word} for {language}", e)
