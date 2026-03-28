# correction_log.py
"""
Correction log endpoints for tracking AI content corrections.

Provides endpoints to:
- Append a new correction log entry (POST, append-only)
- Fetch paginated log entries with optional content_type filter (GET)
"""

from fastapi import APIRouter, HTTPException, Path, Body, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
import logging

from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_CONTENT_TYPES = {"bible_verse", "dictionary_entry", "grammar_category"}


# --- Pydantic Models ---

class AppendCorrectionRequest(BaseModel):
    content_type: str = Field(..., description="bible_verse | dictionary_entry | grammar_category")
    content_reference: Dict[str, Any] = Field(..., description="Reference object (shape varies by content_type)")
    original_text: str = Field(..., min_length=1)
    what_was_wrong: str = Field(..., min_length=1)
    correction: str = Field(..., min_length=1)


class AppendCorrectionResponse(BaseModel):
    success: bool
    log_id: str
    language_code: str


class CorrectionLogEntry(BaseModel):
    id: str
    content_type: str
    content_reference: Dict[str, Any]
    original_text: str
    what_was_wrong: str
    correction: str
    created_at: datetime


class CorrectionLogResponse(BaseModel):
    language_code: str
    entries: List[CorrectionLogEntry]
    total: int
    page: int
    page_size: int


class UpdateWhatWasWrongRequest(BaseModel):
    what_was_wrong: str


# --- Endpoints ---

@router.post("/correction-log/{language}", response_model=AppendCorrectionResponse, status_code=201)
async def append_correction_log(
    language: str = Path(..., description="Language code"),
    request: AppendCorrectionRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> AppendCorrectionResponse:
    """
    Append a correction log entry.

    Each call inserts a new document — entries are never updated, only appended or deleted.

    Raises:
        HTTPException: 400 if content_type invalid, 500 on database error
    """
    try:
        if request.content_type not in VALID_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content_type: {request.content_type}. Must be one of: {sorted(VALID_CONTENT_TYPES)}"
            )

        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        collection = database[Collection.CORRECTION_LOG]

        now = datetime.utcnow()
        doc = {
            "language_code": language_code,
            "content_type": request.content_type,
            "content_reference": request.content_reference,
            "original_text": request.original_text,
            "what_was_wrong": request.what_was_wrong,
            "correction": request.correction,
            "created_at": now
        }

        result = await collection.insert_one(doc)
        log_id = str(result.inserted_id)

        logger.info(f"Appended correction log {log_id} ({request.content_type}) for {language_code}")

        return AppendCorrectionResponse(success=True, log_id=log_id, language_code=language_code)

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Append correction log for {language}", e)


@router.get("/correction-log/{language}", response_model=CorrectionLogResponse)
async def get_correction_log(
    language: str = Path(..., description="Language code"),
    content_type: Optional[str] = Query(None, description="Filter by content_type"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Entries per page"),
    db: MongoDBConnector = Depends(get_db)
) -> CorrectionLogResponse:
    """
    Fetch paginated correction log entries for a language.

    Returns empty entries list (not 404) when no entries exist.

    Raises:
        HTTPException: 400 if content_type invalid, 500 on database error
    """
    try:
        if content_type is not None and content_type not in VALID_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content_type: {content_type}. Must be one of: {sorted(VALID_CONTENT_TYPES)}"
            )

        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        collection = database[Collection.CORRECTION_LOG]

        query: Dict[str, Any] = {"language_code": language_code}
        if content_type:
            query["content_type"] = content_type

        total = await collection.count_documents(query)
        skip = (page - 1) * page_size

        cursor = collection.find(query).sort([("created_at", -1), ("_id", -1)]).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)

        entries = [
            CorrectionLogEntry(
                id=str(doc["_id"]),
                content_type=doc["content_type"],
                content_reference=doc["content_reference"],
                original_text=doc["original_text"],
                what_was_wrong=doc["what_was_wrong"],
                correction=doc["correction"],
                created_at=doc["created_at"]
            )
            for doc in docs
        ]

        logger.info(
            f"Fetched correction log for {language_code}: "
            f"page {page}/{-(-total // page_size) or 1}, {len(entries)} entries"
        )

        return CorrectionLogResponse(
            language_code=language_code,
            entries=entries,
            total=total,
            page=page,
            page_size=page_size
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Fetch correction log for {language}", e)


@router.put("/correction-log/{language}/{log_id}", response_model=AppendCorrectionResponse)
async def update_correction_log_entry(
    language: str = Path(..., description="Language code"),
    log_id: str = Path(..., description="Log entry ObjectId string"),
    request: UpdateWhatWasWrongRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> AppendCorrectionResponse:
    """
    Update the what_was_wrong field of an existing correction log entry.

    All other fields are immutable. Extra body fields are ignored by Pydantic.

    Raises:
        HTTPException: 404 if entry not found or log_id is not a valid ObjectId
        HTTPException: 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')

        try:
            object_id = ObjectId(log_id)
        except InvalidId:
            raise HTTPException(status_code=404, detail=f"Correction log entry {log_id} not found")

        database = db.get_database()
        collection = database[Collection.CORRECTION_LOG]

        result = await collection.update_one(
            {"_id": object_id, "language_code": language_code},
            {"$set": {"what_was_wrong": request.what_was_wrong}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"Correction log entry {log_id} not found")

        logger.info(f"Updated what_was_wrong for correction log {log_id} ({language_code})")

        return AppendCorrectionResponse(success=True, log_id=log_id, language_code=language_code)

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Update correction log {log_id} for {language}", e)
