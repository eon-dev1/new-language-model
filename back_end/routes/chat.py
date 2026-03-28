"""
Chat streaming endpoint.

POST /chat/stream - SSE streaming chat with LLM, tool-use loop, context assembly.

Accepts an optional conversation_id. When provided, the user message and
final assistant response are persisted to the chat_conversations collection.
"""

import json
import logging
import pathlib as _pathlib
from typing import Any, Literal, Optional

from bson import ObjectId
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db_connector.connection import get_mongodb_connector
from shared.tool_registry import get_tools
from shared.system_prompt import SYSTEM_PROMPT
from shared.chat_config import load_config
from shared.llm_tool_loop import (
    run_tool_loop, get_context_window, CONVERSATIONS_COLLECTION, _append_message,
)
from utils.llm_provider import get_provider
from utils.chat_context import assemble_context

logger = logging.getLogger(__name__)
router = APIRouter()

_PROMPTS_DIR = _pathlib.Path(__file__).parent.parent / "prompts"
_TRIOLOGUE_SKILL_PATH = _PROMPTS_DIR / "skills" / "translation-triologue" / "SKILL.md"


def _load_skill(path: _pathlib.Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8").strip()
        logger.info(f"[chat] Loaded skill: {path.parent.name} ({len(content)} chars)")
        return content
    except FileNotFoundError:
        logger.warning(f"[chat] Skill file not found: {path}")
        return None


_TRIOLOGUE_SKILL = _load_skill(_TRIOLOGUE_SKILL_PATH)


class ChatContext(BaseModel):
    language_code: Optional[str] = None
    book_code: Optional[str] = None
    chapter: Optional[int] = None
    view: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: Any  # str or list of content blocks


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: Optional[ChatContext] = None
    conversation_id: Optional[str] = None
    thinking_enabled: bool = False
    chat_mode: Optional[Literal["think", "think_harder", "maximum_thinking", "deep_research"]] = None


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream a chat response with tool-use support via SSE."""

    async def generate():
        try:
            db = await get_mongodb_connector()

            # Assemble data context from MongoDB
            ctx = request.context or ChatContext()
            data_context = await assemble_context(
                db,
                language_code=ctx.language_code,
                book_code=ctx.book_code,
                chapter=ctx.chapter,
                view=ctx.view,
            )

            # Build system prompt: static instructions + data context
            system = SYSTEM_PROMPT
            if data_context:
                system += f"\n\n---\n\nThe user is currently viewing the following data:\n\n{data_context}"

            logger.debug(f"[chat] request: chat_mode={request.chat_mode!r}, thinking_enabled={request.thinking_enabled}")

            provider = get_provider()
            tools = get_tools(readonly=False, translation_only=True)
            context_window = get_context_window()

            # Convert messages to plain dicts
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            # Skill injection for think_harder mode — appended to last user message
            if request.chat_mode == "think_harder" and _TRIOLOGUE_SKILL and messages:
                last_user_idx = next(
                    (i for i in reversed(range(len(messages))) if messages[i]["role"] == "user"),
                    None,
                )
                if last_user_idx is not None:
                    content = messages[last_user_idx]["content"]
                    skill_suffix = (
                        f"\n\n---\n\nUse the following skill to guide your response:\n\n{_TRIOLOGUE_SKILL}"
                    )
                    if isinstance(content, str):
                        messages[last_user_idx]["content"] = content + skill_suffix
                    elif isinstance(content, list):
                        messages[last_user_idx]["content"] = content + [
                            {"type": "text", "text": skill_suffix}
                        ]
                    logger.info(
                        f"[chat] Injected triologue skill into user turn "
                        f"(last_user_idx={last_user_idx}, {len(_TRIOLOGUE_SKILL)} chars)"
                    )
                else:
                    logger.warning("[chat] think_harder: no user message found to inject skill into")
            elif request.chat_mode == "think_harder" and not _TRIOLOGUE_SKILL:
                logger.warning("[chat] think_harder mode requested but triologue skill is not loaded — no injection")

            # Persist user message to conversation if conversation_id provided
            if request.conversation_id and request.messages:
                last_msg = request.messages[-1]
                if last_msg.role == "user" and isinstance(last_msg.content, str):
                    await _append_message(db, request.conversation_id, "user", last_msg.content)

            async for line in run_tool_loop(
                provider, messages, system, tools, db,
                conversation_id=request.conversation_id,
                context_window=context_window,
                thinking_enabled=request.thinking_enabled,
            ):
                yield line

        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Server error: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ToolResultRequest(BaseModel):
    conversation_id: str
    call_id: str
    decision: str  # "approve" or "reject"
    modified_input: Optional[dict] = None


@router.post("/chat/tool-result")
async def chat_tool_result(request: ToolResultRequest):
    """Resume a paused chat stream after user approves/rejects a write tool.

    Returns SSE StreamingResponse continuing the LLM conversation.
    """

    async def generate():
        try:
            db = await get_mongodb_connector()
            coll = db.get_collection(CONVERSATIONS_COLLECTION)

            # Load pending tool call
            conv = await coll.find_one({"_id": ObjectId(request.conversation_id)})
            if not conv or not conv.get("pending_tool_call"):
                yield f"data: {json.dumps({'type': 'error', 'content': 'No pending tool call found'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            pending = conv["pending_tool_call"]
            if pending["call_id"] != request.call_id:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Tool call ID mismatch'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # Execute or reject the tool
            from shared.tool_registry import call_tool
            tool_name = pending["tool_name"]
            if request.decision == "approve":
                tool_input = request.modified_input or pending["input"]
                try:
                    result = await call_tool(tool_name, tool_input, db)
                    tool_content = json.dumps(result, default=str)
                except Exception as e:
                    logger.error(f"Tool execution error ({tool_name}): {e}")
                    tool_content = json.dumps({"error": str(e)})
            else:
                tool_content = json.dumps({"error": "User rejected this action"})

            # Rebuild messages from snapshot, replacing the placeholder result
            messages = pending["messages_snapshot"]

            if messages and messages[-1].get("role") == "user":
                last_content = messages[-1]["content"]
                if isinstance(last_content, list):
                    for item in last_content:
                        if (
                            isinstance(item, dict)
                            and item.get("tool_use_id") == request.call_id
                        ):
                            item["content"] = tool_content
                            break

            # Clear pending tool call
            await coll.update_one(
                {"_id": ObjectId(request.conversation_id)},
                {"$unset": {"pending_tool_call": ""}},
            )

            # Resume via shared tool loop
            provider = get_provider()
            tools = get_tools(readonly=False, translation_only=True)
            context_window = get_context_window()

            # Use assembled system prompt if stored, otherwise bare SYSTEM_PROMPT
            system = pending.get("system_prompt", SYSTEM_PROMPT)
            thinking_enabled = pending.get("thinking_enabled", False)

            async for line in run_tool_loop(
                provider, messages, system, tools, db,
                conversation_id=request.conversation_id,
                context_window=context_window,
                thinking_enabled=thinking_enabled,
            ):
                yield line

        except Exception as e:
            logger.error(f"Chat tool-result stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Server error: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
