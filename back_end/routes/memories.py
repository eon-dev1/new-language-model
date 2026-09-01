# memories.py
"""
Notes endpoints for per-language free-form notes.

Provides endpoints to:
- Fetch all notes for a language
- Create a new note
- Update an existing note by UUID
- Delete a note by UUID
"""

from fastapi import APIRouter, HTTPException, Path, Body, Depends
from pydantic import BaseModel, Field, field_validator
from typing import List
from datetime import datetime, timezone
import logging
import uuid

from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)

TITLE_MAX = 200


# --- Pydantic Models ---

class NoteItem(BaseModel):
    """A single language note."""
    id: str
    title: str = Field(..., min_length=1, max_length=TITLE_MAX)
    text: str
    created_at: datetime
    updated_at: datetime


class NotesResponse(BaseModel):
    """Response containing all notes for a language."""
    language_code: str
    notes: List[NoteItem]
    count: int


class CreateNoteRequest(BaseModel):
    title: str = Field(..., max_length=TITLE_MAX)
    text: str

    @field_validator("title", "text")
    @classmethod
    def _strip_and_require(cls, v: str) -> str:
        # Strip first, then enforce non-empty. Field(min_length=1) alone would
        # accept "   " and let the route store an effectively empty value that
        # would then fail the next GET via NoteItem(min_length=1).
        v = v.strip()
        if not v:
            raise ValueError("must be non-empty after stripping whitespace")
        return v


class NoteActionResponse(BaseModel):
    """Response confirming a note action."""
    success: bool
    note_id: str
    language_code: str


# --- Endpoints ---

@router.get("/memories/{language}/notes", response_model=NotesResponse)
async def get_notes(
    language: str = Path(..., description="Language code"),
    db: MongoDBConnector = Depends(get_db)
) -> NotesResponse:
    """
    Fetch all notes for a language.

    Returns an empty notes array (not 404) if no notes document exists yet.

    Raises:
        HTTPException: 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        collection = database[Collection.LANGUAGE_NOTES]

        doc = await collection.find_one({"language_code": language_code})

        if not doc:
            logger.info(f"No notes document for {language_code}, returning empty")
            return NotesResponse(language_code=language_code, notes=[], count=0)

        notes = [
            NoteItem(
                id=n["id"],
                title=n.get("title", ""),
                text=n.get("text", ""),
                created_at=n["created_at"],
                updated_at=n["updated_at"]
            )
            for n in doc.get("notes", [])
        ]

        return NotesResponse(language_code=language_code, notes=notes, count=len(notes))

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Fetch notes for {language}", e)


@router.post("/memories/{language}/notes", response_model=NoteActionResponse)
async def create_note(
    language: str = Path(..., description="Language code"),
    request: CreateNoteRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> NoteActionResponse:
    """
    Create a new note for a language.

    Upserts the language notes document if it does not exist yet.

    Raises:
        HTTPException: 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        collection = database[Collection.LANGUAGE_NOTES]

        now = datetime.now(timezone.utc)
        note_id = str(uuid.uuid4())
        new_note = {
            "id": note_id,
            "title": request.title,
            "text": request.text,
            "created_at": now,
            "updated_at": now
        }

        result = await collection.update_one(
            {"language_code": language_code},
            {
                "$push": {"notes": new_note},
                "$set": {"updated_at": now},
                "$setOnInsert": {"language_code": language_code}
            },
            upsert=True
        )

        if result.matched_count == 0 and result.upserted_id is None:
            raise HTTPException(status_code=500, detail="Failed to create note")

        logger.info(f"Created note {note_id} for {language_code}")

        return NoteActionResponse(success=True, note_id=note_id, language_code=language_code)

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Create note for {language}", e)


@router.put("/memories/{language}/notes/{note_id}", response_model=NoteActionResponse)
async def update_note(
    language: str = Path(..., description="Language code"),
    note_id: str = Path(..., description="Note UUID"),
    request: CreateNoteRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> NoteActionResponse:
    """
    Update the text of an existing note.

    Raises:
        HTTPException: 404 if note not found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        collection = database[Collection.LANGUAGE_NOTES]

        now = datetime.now(timezone.utc)

        result = await collection.update_one(
            {"language_code": language_code, "notes.id": note_id},
            {
                "$set": {
                    "notes.$.title": request.title,
                    "notes.$.text": request.text,
                    "notes.$.updated_at": now,
                    "updated_at": now
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Note {note_id} not found for {language_code}"
            )

        logger.info(f"Updated note {note_id} for {language_code}")

        return NoteActionResponse(success=True, note_id=note_id, language_code=language_code)

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Update note {note_id} for {language}", e)


@router.delete("/memories/{language}/notes/{note_id}", response_model=NoteActionResponse)
async def delete_note(
    language: str = Path(..., description="Language code"),
    note_id: str = Path(..., description="Note UUID"),
    db: MongoDBConnector = Depends(get_db)
) -> NoteActionResponse:
    """
    Delete a note by UUID.

    Raises:
        HTTPException: 404 if note not found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        collection = database[Collection.LANGUAGE_NOTES]

        now = datetime.now(timezone.utc)

        result = await collection.update_one(
            {"language_code": language_code, "notes.id": note_id},
            {
                "$pull": {"notes": {"id": note_id}},
                "$set": {"updated_at": now}
            }
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Note {note_id} not found for {language_code}"
            )

        logger.info(f"Deleted note {note_id} for {language_code}")

        return NoteActionResponse(success=True, note_id=note_id, language_code=language_code)

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Delete note {note_id} for {language}", e)
