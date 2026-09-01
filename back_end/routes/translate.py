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
from shared.system_prompt import SYSTEM_PROMPT, load_skill, compose_prompt
from shared.tool_registry import get_tools
from utils.llm_provider import get_provider, ProviderConfigError

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-process HMAC key for signing batch system prompts.
# Now vestigial — signs a static server-known constant (_BATCH_SYSTEM)
# rather than a per-batch unique string. Kept for backward compatibility
# with the client echo/verify flow.
_BATCH_HMAC_KEY = os.urandom(32)


def _sign_prompt(prompt: str) -> str:
    return hmac.new(_BATCH_HMAC_KEY, prompt.encode(), hashlib.sha256).hexdigest()


def _verify_prompt(prompt: str, signature: str) -> bool:
    expected = hmac.new(_BATCH_HMAC_KEY, prompt.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Composed system prompts (pre-computed at import, not per request) ─────────

_VERSE_SKILL = load_skill("verse-translation")
if not _VERSE_SKILL:
    logger.error(
        "verse-translation/SKILL.md not found — "
        "batch translation will run without approval loop guidance"
    )

_BATCH_SYSTEM = compose_prompt(SYSTEM_PROMPT, skill=_VERSE_SKILL)
_BATCH_SYSTEM_SIG = _sign_prompt(_BATCH_SYSTEM)


# Tool subset focused on translation context gathering
TRANSLATION_TOOL_NAMES = {
    "get_language_info",
    "get_parallel_verses",
    "list_dictionary_entries",
    "get_dictionary_entry",
    "list_grammar_categories",
    "get_grammar_category",
    "get_word_index",
    "get_phrase_context",
    "search_language_notes",
    "search_correction_log",
    "propose_verse_translation",   # Terminal write tool
}


def get_translation_tools() -> list[dict]:
    """Return tool subset relevant to verse translation (includes propose_verse_translation)."""
    all_tools = get_tools(readonly=False, translation_only=True)
    return [t for t in all_tools if t["name"] in TRANSLATION_TOOL_NAMES]


# ── User message builders (extracted for testability) ─────────────────────────

def _build_single_verse_user_message(
    book_name: str, chapter: int, verse: int,
    language_name: str, language_code: str, english_text: str,
) -> str:
    return (
        f"Please translate {book_name} {chapter}:{verse} "
        f"into {language_name} (language code: {language_code}).\n\n"
        f"English: \"{english_text}\""
    )


def _build_batch_user_message(
    book_name: str, chapter: int,
    language_name: str, language_code: str,
    verses: list,
) -> str:
    verse_list = "\n".join(
        f"  Verse {v.verse_number}: \"{v.english_text}\""
        for v in verses
    )
    return (
        f"Please translate the following {len(verses)} verse(s) from "
        f"{book_name} chapter {chapter} into {language_name} "
        f"(language code: {language_code}), one at a time.\n\n"
        f"Verses to translate:\n{verse_list}\n\n"
        f"Start with the first untranslated verse."
    )


# ── Pydantic models ──────────────────────────────────────────────────────────

class TranslateVerseRequest(BaseModel):
    english_text: str
    language_name: str   # e.g. "Bughotu" — from BibleReader props
    book_name: str       # e.g. "John" — from selectedBook.book_name


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

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

            system = SYSTEM_PROMPT

            messages = [{
                "role": "user",
                "content": _build_single_verse_user_message(
                    request.book_name, chapter, verse,
                    request.language_name, language_code, request.english_text,
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
                pace_seconds=2.0,              # Rate limit mitigation (30K TPM tier)
            ):
                yield line

        except ProviderConfigError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception:
            logger.exception("Translation stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Server error'})}\n\n"
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

            system = _BATCH_SYSTEM

            # Emit static system prompt + pre-signed HMAC — frontend echoes both back on every resume call
            yield f"data: {json.dumps({'type': 'batch_system_prompt', 'system': system, 'system_prompt_sig': _BATCH_SYSTEM_SIG})}\n\n"

            messages = [{
                "role": "user",
                "content": _build_batch_user_message(
                    request.book_name, chapter,
                    request.language_name, language_code,
                    request.verses,
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
                    pace_seconds=2.0,              # Rate limit mitigation (30K TPM tier)
                ),
                messages,
            ):
                yield line

        except ProviderConfigError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception:
            logger.exception("Batch translation stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Server error'})}\n\n"
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
                    pace_seconds=2.0,              # Rate limit mitigation (30K TPM tier)
                ),
                messages,
            ):
                yield line

        except ProviderConfigError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception:
            logger.exception("Batch resume stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Server error'})}\n\n"
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
