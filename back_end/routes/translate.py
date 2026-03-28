"""
Streaming verse translation endpoints.

Single-verse:
  POST /api/verses/{language}/{book_code}/{chapter}/{verse}/translate-stream

Batch (multi-verse, stateful feedback loop):
  POST /api/verses/{language}/{book_code}/{chapter}/translate-batch-stream
  POST /api/verses/{language}/{book_code}/{chapter}/translate-batch-resume

Batch architecture:
  - LLM gathers context for ALL selected verses in one session
  - Proposes them one at a time (write tool = approval gate per verse)
  - Frontend holds messages snapshot between resumes (from tool_approval event)
  - Translator rejection/correction feedback injected before each resume
  - Subsequent proposals informed by all prior decisions in the conversation

Context window: 200K tokens (Anthropic) / 128K (local LLM).
Budget limit: 80% — leaves 20% for reasoning and output.
"""

import hashlib
import hmac
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db_connector.connection import get_mongodb_connector
from shared.llm_tool_loop import run_tool_loop, get_context_window
from shared.tool_registry import get_tools
from utils.llm_provider import get_provider

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-process HMAC key for signing batch system prompts.
# Prevents a client from swapping the system prompt between batch resume calls.
_BATCH_HMAC_KEY = os.urandom(32)


def _sign_prompt(prompt: str) -> str:
    return hmac.new(_BATCH_HMAC_KEY, prompt.encode(), hashlib.sha256).hexdigest()


def _verify_prompt(prompt: str, signature: str) -> bool:
    expected = hmac.new(_BATCH_HMAC_KEY, prompt.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

# Tool subset focused on translation context gathering
TRANSLATION_TOOL_NAMES = {
    "get_language_info",
    "get_parallel_verses",
    "list_dictionary_entries",
    "get_dictionary_entry",
    "list_grammar_categories",
    "get_grammar_category",
    "get_word_index",
    "propose_verse_translation",   # Terminal write tool
}


def get_translation_tools() -> list[dict]:
    """Return tool subset relevant to verse translation (includes propose_verse_translation)."""
    all_tools = get_tools(readonly=False, translation_only=True)
    return [t for t in all_tools if t["name"] in TRANSLATION_TOOL_NAMES]


# NOTE: {english_text} is intentionally NOT a format slot in this template.
# Stored english_text is clean (USFM importer strips all backslash markers and
# Strong's numbers). But keeping english_text out of the template entirely is the
# correct structural pattern — it never touches str.format(), so any edge case
# (HTML import, future paths) is handled safely.
# english_text appears only in the user message (plain f-string — no format risk).
TRANSLATION_SYSTEM_PROMPT = """
You are a specialized Bible translator for {language_name} ({language_code}).

Task: Translate ONE verse from English into {language_name}.

Verse: {book_name} {chapter}:{verse}

## Strategy
1. Call get_parallel_verses to compare this passage across available languages — find convergent and divergent translation patterns
2. Look up key terms via get_dictionary_entry and get_word_index to identify established vocabulary in {language_name}
3. Check get_grammar_category (morphology, syntax) if sentence structure is uncertain
4. Continue gathering context UNTIL:
   - You have HIGH CONFIDENCE in the translation, OR
   - The system signals context budget is running low
5. Call propose_verse_translation with your translation, confidence (0.0-1.0), and brief rationale

Prioritize faithfulness and natural expression in {language_name}.
""".strip()


class TranslateVerseRequest(BaseModel):
    english_text: str
    language_name: str   # e.g. "Bughotu" — from BibleReader props
    book_name: str       # e.g. "John" — from selectedBook.book_name


# NOTE: {verse_list} is safe as a format slot.
# verse_list is pre-built via str.join (not embedded in the template directly).
# str.format() processes the template once and does NOT re-parse substituted values,
# so {these} inside english_text content is never seen as a format specifier.
BATCH_TRANSLATION_SYSTEM_PROMPT = """
You are a specialized Bible translator for {language_name} ({language_code}).

Task: Translate {verse_count} verse(s) from {book_name} chapter {chapter} into {language_name}.

Verses to translate (in order):
{verse_list}

## Strategy
1. Call get_parallel_verses for this chapter range — gather context for ALL verses at once
2. Look up key shared vocabulary via get_dictionary_entry and get_word_index
3. Check get_grammar_category (morphology, syntax) if sentence structure is uncertain
4. Once you have sufficient shared context, translate verse by verse:
   - Call propose_verse_translation for the FIRST untranslated verse
   - ALWAYS include verse_number in the call — it is required for frontend routing
   - Wait for human review (you will see approval/rejection + optional feedback)
   - Apply any translator corrections or insights to the remaining verses before proceeding
5. Continue until all {verse_count} verse(s) are proposed

Prioritize faithfulness and natural expression in {language_name}.
Translator corrections on earlier verses should directly inform your choices for later verses.
""".strip()


class BatchVerseItem(BaseModel):
    verse_number: int
    english_text: str


class TranslateBatchRequest(BaseModel):
    verses: list[BatchVerseItem] = Field(..., max_length=500)   # All verses selected for translation
    language_name: str             # e.g. "Bughotu"
    book_name: str                 # e.g. "John"


class BatchResumeRequest(BaseModel):
    messages: list[dict]           # Full conversation snapshot (from tool_approval.messages_snapshot)
    system_prompt: str             # Echoed back from batch_system_prompt SSE event
    system_prompt_sig: str         # HMAC signature of system_prompt — prevents client-side tampering
    call_id: str                   # The tool_use_id of the just-reviewed proposal
    verse_number: int              # Which verse was just reviewed
    decision: str                  # "approve" or "reject" ONLY
    feedback: Optional[str] = None  # Translator comment or corrected text (for "reject" path)


@router.post("/verses/{language}/{book_code}/{chapter}/{verse}/translate-stream")
async def translate_verse_stream(
    language: str,
    book_code: str,
    chapter: int,
    verse: int,
    request: TranslateVerseRequest,
):
    """SSE streaming endpoint for agentic verse translation with context gathering."""

    async def generate():
        try:
            language_code = language.lower().replace(' ', '_').replace('-', '_')
            db = await get_mongodb_connector()

            # Format system prompt — english_text is NOT a slot here (see module docstring)
            system = TRANSLATION_SYSTEM_PROMPT.format(
                language_name=request.language_name,
                language_code=language_code,
                book_name=request.book_name,
                chapter=chapter,
                verse=verse,
            )

            # english_text goes in the user message as a plain f-string — safe for any input
            messages = [{
                "role": "user",
                "content": (
                    f"Please translate {request.book_name} {chapter}:{verse} "
                    f"into {request.language_name}.\n\nEnglish: \"{request.english_text}\""
                ),
            }]

            provider = get_provider()
            tools = get_translation_tools()
            context_window = get_context_window()

            async for line in run_tool_loop(
                provider, messages, system, tools, db,
                conversation_id=None,          # No chat persistence
                context_window=context_window,
                thinking_enabled=False,        # Explicit: no thinking for translation
                pace_seconds=2.0,
            ):
                yield line

        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Translation stream error: {e}")
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


def _wrap_with_messages_snapshot(tool_loop_gen, messages: list):
    """
    Async generator that intercepts tool_approval events from run_tool_loop
    and injects messages_snapshot into them.

    Called by both batch endpoints. messages is the same list passed to
    run_tool_loop — it is mutated in-place by the loop, so by the time
    tool_approval is yielded, the list already contains the complete conversation.

    run_tool_loop itself is NOT modified — this wrapper keeps chat route
    tool_approval events clean (no 50-100KB message history appended).
    """
    return _messages_snapshot_gen(tool_loop_gen, messages)


async def _messages_snapshot_gen(tool_loop_gen, messages: list):
    async for line in tool_loop_gen:
        if line.startswith('data: '):
            try:
                event = json.loads(line[6:].rstrip('\n'))
                if event.get('type') == 'tool_approval':
                    event['messages_snapshot'] = messages
                    yield f"data: {json.dumps(event)}\n\n"
                    continue
            except (json.JSONDecodeError, KeyError):
                pass
        yield line


@router.post("/verses/{language}/{book_code}/{chapter}/translate-batch-stream")
async def translate_batch_stream(
    language: str,
    book_code: str,
    chapter: int,
    request: TranslateBatchRequest,
):
    """SSE streaming endpoint to start a multi-verse batch translation session."""

    async def generate():
        try:
            language_code = language.lower().replace(' ', '_').replace('-', '_')
            db = await get_mongodb_connector()

            # verse_list is built before .format() — safe for english_text with { }
            verse_list = "\n".join(
                f"  Verse {v.verse_number}: \"{v.english_text}\""
                for v in request.verses
            )

            system = BATCH_TRANSLATION_SYSTEM_PROMPT.format(
                language_name=request.language_name,
                language_code=language_code,
                book_name=request.book_name,
                chapter=chapter,
                verse_count=len(request.verses),
                verse_list=verse_list,
            )

            # Emit system prompt + HMAC signature — frontend echoes both back on every resume call
            yield f"data: {json.dumps({'type': 'batch_system_prompt', 'system': system, 'system_prompt_sig': _sign_prompt(system)})}\n\n"

            messages = [{
                "role": "user",
                "content": (
                    f"Please translate the following {len(request.verses)} verse(s) from "
                    f"{request.book_name} chapter {chapter} into {request.language_name}, "
                    f"one at a time, starting with verse {request.verses[0].verse_number}."
                ),
            }]

            provider = get_provider()
            tools = get_translation_tools()
            context_window = get_context_window()

            async for line in _messages_snapshot_gen(
                run_tool_loop(
                    provider, messages, system, tools, db,
                    conversation_id=None,
                    context_window=context_window,
                    thinking_enabled=False,
                    pace_seconds=2.0,
                ),
                messages,
            ):
                yield line

        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Batch translation stream error: {e}")
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


@router.post("/verses/{language}/{book_code}/{chapter}/translate-batch-resume")
async def translate_batch_resume(
    language: str,
    book_code: str,
    chapter: int,
    request: BatchResumeRequest,
):
    """Resume a batch session after the user approves or rejects a verse proposal."""

    if not _verify_prompt(request.system_prompt, request.system_prompt_sig):
        raise HTTPException(status_code=400, detail="Invalid system prompt signature")

    async def generate():
        try:
            db = await get_mongodb_connector()
            messages = request.messages

            # Replace awaiting_approval placeholder with actual decision result
            if messages and messages[-1].get("role") == "user":
                for item in messages[-1].get("content", []):
                    if isinstance(item, dict) and item.get("tool_use_id") == request.call_id:
                        item["content"] = json.dumps({
                            "status": request.decision,
                            "verse_number": request.verse_number,
                        })
                        break

            # Inject translator feedback as explicit context before LLM continues.
            # Only on "reject" — "approve" means accepted as-is, no correction needed.
            if request.feedback and request.decision == "reject":
                messages.append({
                    "role": "user",
                    "content": (
                        f"Translator feedback on verse {request.verse_number}: "
                        f"{request.feedback}. "
                        f"Apply this insight when translating the remaining verses."
                    ),
                })

            provider = get_provider()
            tools = get_translation_tools()
            context_window = get_context_window()

            async for line in _messages_snapshot_gen(
                run_tool_loop(
                    provider, messages, system=request.system_prompt, tools=tools, db=db,
                    conversation_id=None,
                    context_window=context_window,
                    thinking_enabled=False,
                    pace_seconds=2.0,
                ),
                messages,
            ):
                yield line

        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Batch resume stream error: {e}")
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
