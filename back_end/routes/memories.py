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
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging
import uuid

from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Pydantic Models ---

class NoteItem(BaseModel):
    """A single language note."""
    id: str
    text: str
    created_at: datetime
    updated_at: datetime


class NotesResponse(BaseModel):
    """Response containing all notes for a language."""
    language_code: str
    notes: List[NoteItem]
    count: int


class CreateNoteRequest(BaseModel):
    text: str = Field(..., min_length=1)


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
                text=n["text"],
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

        now = datetime.utcnow()
        note_id = str(uuid.uuid4())
        new_note = {
            "id": note_id,
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

        now = datetime.utcnow()

        result = await collection.update_one(
            {"language_code": language_code, "notes.id": note_id},
            {
                "$set": {
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

        now = datetime.utcnow()

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
