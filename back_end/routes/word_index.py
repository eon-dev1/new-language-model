"""
Word index management endpoints.

POST /word-index/rebuild  - Rebuild word index for a specific language
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db_connector.connection import MongoDBConnector
from constants import Collection
from utils.word_index.builder import build_word_index
from .dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class RebuildRequest(BaseModel):
    language_code: str


@router.post("/word-index/rebuild")
async def rebuild_word_index(
    request: RebuildRequest,
    db: MongoDBConnector = Depends(get_db),
):
    """Rebuild word index for a specific language. Troubleshooting escape hatch."""
    languages_col = db.get_collection(Collection.LANGUAGES)
    lang_doc = await languages_col.find_one({"language_code": request.language_code})

    if not lang_doc:
        raise HTTPException(status_code=404, detail=f"Language '{request.language_code}' not found")

    if lang_doc.get("is_base_language"):
        raise HTTPException(status_code=400, detail="Cannot rebuild index for base language (English)")

    try:
        result = await build_word_index(db, request.language_code)
        logger.info(f"Word index rebuilt for {request.language_code}: {result['words_indexed']} words")
        return {"success": True, "language_code": request.language_code, **result}
    except Exception as e:
        logger.error(f"Word index rebuild failed for {request.language_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
