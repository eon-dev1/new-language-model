"""
Shared LLM streaming tool-loop for NLM.

Extracted from routes/chat.py to allow reuse by the verse-translation endpoint
(routes/translate.py) without duplicating the loop, budget logic, or persistence
helpers.

Used by:
- routes/chat.py     — general chat with full conversation persistence
- routes/translate.py — stateless verse translation (conversation_id=None)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from bson import ObjectId

from shared.chat_config import load_config
from shared.tool_registry import call_tool, is_write_tool

logger = logging.getLogger(__name__)

CONVERSATIONS_COLLECTION = "chat_conversations"

# --- Context budget constants ---
MAX_TOOL_RESULT_CHARS = 25_000
MAX_TOTAL_RESULT_CHARS = 500_000
CONTEXT_BUDGET_PERCENT = 0.80
MAX_TOOL_CALLS = 50

LOCAL_DEFAULT_CONTEXT = 128_000


def get_context_window() -> int:
    """Return the context window size based on current provider config."""
    from shared import model_registry

    config = load_config()
    provider_type = config.get("llm_provider", "openrouter")

    if provider_type == "local":
        return config.get("local_context_window", LOCAL_DEFAULT_CONTEXT)

    model_key = "openrouter_model"
    return model_registry.get_context_window(config.get(model_key, ""))


def _truncate_tool_result(result_str: str) -> str:
    """Truncate a tool result string to MAX_TOOL_RESULT_CHARS with boundary-aware cut."""
    if len(result_str) <= MAX_TOOL_RESULT_CHARS:
        return result_str
    # Try to find a clean JSON boundary (end of object/array element)
    cut = result_str.rfind('},', 0, MAX_TOOL_RESULT_CHARS)
    if cut > MAX_TOOL_RESULT_CHARS * 0.5:
        return result_str[:cut + 1] + ']\n\n[Result truncated — exceeded 25K char limit]'
    # Fallback: raw character cut
    return result_str[:MAX_TOOL_RESULT_CHARS] + '\n\n[Result truncated — exceeded 25K char limit]'


async def run_tool_loop(
    provider,
    messages: list[dict],
    system: str,
    tools: list[dict],
    db,
    conversation_id: str | None = None,
    context_window: int = 200_000,
    thinking_enabled: bool = False,
    pace_seconds: float = 0,
) -> AsyncGenerator[str, None]:
    """Shared LLM streaming + tool execution loop. Yields SSE data lines.

    Handles: text streaming, tool execution, write-tool approval gate,
    per-result truncation, and three-layer context budget.

    When conversation_id is None, all persistence is skipped (stateless mode
    used by the translation endpoint).
    """
    full_response_text = ""
    full_thinking_text = ""
    response_tool_calls: list[str] = []
    tool_call_count = 0
    total_result_chars = 0
    current_input_tokens = 0
    iteration = 0

    while True:
        if iteration > 0 and pace_seconds > 0:
            logger.debug(f"[tool_loop] pacing {pace_seconds}s before iteration {iteration}")
            await asyncio.sleep(pace_seconds)
        iteration += 1

        collected_text = ""
        tool_calls = []
        thinking_blocks: list[dict] = []

        async for event in provider.stream_chat(messages, system, tools, thinking_enabled=thinking_enabled):
            if event["type"] == "text":
                collected_text += event["content"]
                yield f"data: {json.dumps(event)}\n\n"

            elif event["type"] == "thinking_delta":
                full_thinking_text += event["content"]
                yield f"data: {json.dumps(event)}\n\n"

            elif event["type"] == "thinking_block":
                thinking_blocks.append({
                    "type": "thinking",
                    "thinking": event["thinking"],
                    "signature": event["signature"],
                })

            elif event["type"] == "tool_use":
                tool_calls.append(event)

            elif event["type"] == "tool_use_start":
                yield f"data: {json.dumps({'type': 'tool_call', 'name': event['name']})}\n\n"

            elif event["type"] == "usage":
                current_input_tokens = event["input_tokens"]
                context_payload: dict = {
                    "type": "context_usage",
                    "input_tokens": current_input_tokens,
                    "max_tokens": context_window,
                }
                if event.get("cache_creation_input_tokens"):
                    context_payload["cache_creation_input_tokens"] = event["cache_creation_input_tokens"]
                if event.get("cache_read_input_tokens"):
                    context_payload["cache_read_input_tokens"] = event["cache_read_input_tokens"]
                yield f"data: {json.dumps(context_payload)}\n\n"

            elif event["type"] == "error":
                yield f"data: {json.dumps(event)}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            elif event["type"] == "done":
                pass

        full_response_text += collected_text

        # No tool calls — we're done
        if not tool_calls:
            if conversation_id and full_response_text:
                await _append_message(
                    db, conversation_id, "assistant",
                    full_response_text, response_tool_calls or None,
                    thinking_content=full_thinking_text or None,
                )
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Track tool names for persistence
        for tc in tool_calls:
            response_tool_calls.append(tc["name"])

        # --- Budget checks (three layers) ---
        tool_call_count += len(tool_calls)

        # Primary: token-based budget
        if current_input_tokens > context_window * CONTEXT_BUDGET_PERCENT:
            msg = "\n\n[Context budget reached — stopping tool calls]"
            full_response_text += msg
            if conversation_id:
                await _append_message(
                    db, conversation_id, "assistant",
                    full_response_text, response_tool_calls or None,
                    thinking_content=full_thinking_text or None,
                )
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Secondary: cumulative character budget
        if total_result_chars > MAX_TOTAL_RESULT_CHARS:
            msg = "\n\n[Tool result size limit reached]"
            full_response_text += msg
            if conversation_id:
                await _append_message(
                    db, conversation_id, "assistant",
                    full_response_text, response_tool_calls or None,
                    thinking_content=full_thinking_text or None,
                )
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Backstop: hard call count
        if tool_call_count > MAX_TOOL_CALLS:
            msg = "\n\n[Tool call limit reached]"
            full_response_text += msg
            if conversation_id:
                await _append_message(
                    db, conversation_id, "assistant",
                    full_response_text, response_tool_calls or None,
                    thinking_content=full_thinking_text or None,
                )
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Build assistant content: thinking blocks first (required by Anthropic API), then text and tool_use
        assistant_content = []
        for tb in thinking_blocks:
            assistant_content.append(tb)
        if collected_text:
            assistant_content.append({"type": "text", "text": collected_text})
        for tc in tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute tools — reads run immediately, first write pauses for approval
        tool_results = []
        pending_write = None

        for tc in tool_calls:
            name = tc["name"]

            if is_write_tool(name):
                if pending_write is None:
                    pending_write = tc
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps({"status": "awaiting_approval"}),
                })
                continue

            # Execute read tools regardless of position
            try:
                result = await call_tool(name, tc["input"], db)
                result_str = _truncate_tool_result(json.dumps(result, default=str))
                _preview = result_str[:500]
                yield f"data: {json.dumps({'type': 'tool_result', 'name': name, 'preview': _preview})}\n\n"
                total_result_chars += len(result_str)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": result_str,
                })
            except Exception as e:
                logger.exception(f"Tool call error ({name})")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    # Exception class only — enough for the model to tell a malformed-argument
                    # TypeError from a data-layer failure, without relaying exception text.
                    "content": json.dumps({"error": f"Tool '{name}' failed ({type(e).__name__})"}),
                })

        # If a write tool needs approval, save state and pause
        if pending_write is not None:
            messages.append({"role": "user", "content": tool_results})

            if conversation_id:
                await _save_pending_tool_call(
                    db, conversation_id, messages, pending_write, system,
                    thinking_enabled=thinking_enabled,
                )

            yield f"data: {json.dumps({'type': 'tool_approval', 'call_id': pending_write['id'], 'tool_name': pending_write['name'], 'input': pending_write['input']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        messages.append({"role": "user", "content": tool_results})

        # Loop continues — provider will generate response with tool results


async def _save_pending_tool_call(
    db, conversation_id: str, messages: list[dict], tool_call: dict,
    system_prompt: str | None = None,
    thinking_enabled: bool = False,
) -> None:
    """Save conversation state so a paused write-tool stream can be resumed."""
    try:
        coll = db.get_collection(CONVERSATIONS_COLLECTION)
        pending_data: dict[str, Any] = {
            "call_id": tool_call["id"],
            "tool_name": tool_call["name"],
            "input": tool_call["input"],
            "messages_snapshot": messages,  # Anthropic-format
            "thinking_enabled": thinking_enabled,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if system_prompt:
            pending_data["system_prompt"] = system_prompt
        await coll.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {
                "pending_tool_call": pending_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as e:
        logger.warning(f"Failed to save pending tool call: {e}")


async def _append_message(
    db, conversation_id: str, role: str, content: str,
    tool_calls: list[str] | None = None,
    thinking_content: str | None = None,
) -> None:
    """Append a message to a conversation and update metadata."""
    try:
        coll = db.get_collection(CONVERSATIONS_COLLECTION)
        msg: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if thinking_content:
            msg["thinking_content"] = thinking_content

        await coll.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$push": {"messages": msg},
                "$inc": {"message_count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )
    except Exception as e:
        logger.warning(f"Failed to persist message to conversation {conversation_id}: {e}")
