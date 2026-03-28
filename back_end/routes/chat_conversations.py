"""
Chat conversation persistence endpoints.

CRUD for chat_conversations collection in MongoDB.
Conversations are global (not scoped to a language).
App context is sent per-message, not per-conversation.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db_connector.connection import MongoDBConnector
from routes.dependencies import get_db, api_error

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION = "chat_conversations"


class ConversationCreate(BaseModel):
    title: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/chat/conversations")
async def list_conversations(db: MongoDBConnector = Depends(get_db)):
    """List all conversations, newest first."""
    try:
        coll = db.get_collection(COLLECTION)
        cursor = coll.find(
            {},
            {"title": 1, "created_at": 1, "updated_at": 1, "message_count": 1},
        ).sort("updated_at", -1)
        docs = await cursor.to_list(length=100)

        return [
            {
                "id": str(doc["_id"]),
                "title": doc.get("title", "Untitled"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "message_count": doc.get("message_count", 0),
            }
            for doc in docs
        ]
    except Exception as e:
        raise api_error("list conversations", e)


@router.post("/chat/conversations")
async def create_conversation(
    body: ConversationCreate,
    db: MongoDBConnector = Depends(get_db),
):
    """Create a new conversation. Returns the new conversation ID."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "title": body.title or "New conversation",
            "messages": [],
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        coll = db.get_collection(COLLECTION)
        result = await coll.insert_one(doc)
        return {"id": str(result.inserted_id)}
    except Exception as e:
        raise api_error("create conversation", e)


@router.get("/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: MongoDBConnector = Depends(get_db),
):
    """Get a conversation with full message history."""
    try:
        coll = db.get_collection(COLLECTION)
        doc = await coll.find_one({"_id": ObjectId(conversation_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {
            "id": str(doc["_id"]),
            "title": doc.get("title", "Untitled"),
            "messages": doc.get("messages", []),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise api_error("get conversation", e)


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: MongoDBConnector = Depends(get_db),
):
    """Delete a conversation."""
    try:
        coll = db.get_collection(COLLECTION)
        result = await coll.delete_one({"_id": ObjectId(conversation_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise api_error("delete conversation", e)


@router.patch("/chat/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    body: ConversationCreate,
    db: MongoDBConnector = Depends(get_db),
):
    """Update conversation title."""
    try:
        coll = db.get_collection(COLLECTION)
        result = await coll.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$set": {
                    "title": body.title or "Untitled",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"updated": True}
    except HTTPException:
        raise
    except Exception as e:
        raise api_error("update conversation title", e)
