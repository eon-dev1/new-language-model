# Chat & AI Translation System

## Overview

The NLM backend provides AI-assisted translation through two streaming endpoints:

1. **General chat** (`POST /api/chat/stream`) — open-ended conversation with tool access to all project data
2. **Verse translation** (`POST /api/verses/.../translate-stream`, `translate-batch-stream`, `translate-batch-resume`) — focused translation workflow with approval gate per verse

Both share the same core infrastructure: an LLM provider abstraction, a streaming tool-use loop, and a tool registry.

## Architecture

```
Frontend (ChatDrawer / BibleReader)
    |
    | POST /api/chat/stream  or  /api/verses/.../translate-*-stream
    | (SSE — Server-Sent Events)
    v
+--------------------------------------------------+
|  routes/chat.py  or  routes/translate.py          |
|  - Assembles system prompt and context            |
|  - Gets provider from config                      |
|  - Calls run_tool_loop()                          |
+--------------------------------------------------+
    |
    v
+--------------------------------------------------+
|  shared/llm_tool_loop.py                          |
|  - Async generator yielding SSE events            |
|  - Executes read tools automatically              |
|  - Pauses on write tools for approval             |
|  - Three-layer context budget                     |
+--------------------------------------------------+
    |                         |
    v                         v
+------------------+  +------------------+
| utils/           |  | shared/          |
| llm_provider.py  |  | tool_registry.py |
| - Anthropic SDK  |  | - 20 tools       |
| - Local LLM      |  | - read/write     |
+------------------+  | - dispatch       |
                      +------------------+
                              |
                              v
                      MongoDB (via MCP tool implementations)
```

## LLM Provider (`utils/llm_provider.py`)

A single `AnthropicProvider` class handles both Anthropic API and local LLM servers. Both use the Anthropic Messages API format — llama.cpp supports `/v1/messages` natively.

| Provider | `api_key` | `base_url` | Thinking |
|----------|-----------|------------|----------|
| Anthropic | Real API key | None (default) | Enabled (except Haiku) |
| Local | `"local"` (placeholder) | e.g. `http://127.0.0.1:8080` | Disabled |

**Thinking support**: When enabled, uses beta header `interleaved-thinking-2025-05-14` with a budget of 8,000 tokens and max output of 16,192 tokens. Auto-disabled for local providers and Haiku models.

**Configuration** is loaded from `~/.nlm/chat_config.json` via `shared/chat_config.py`:

```json
{
  "llm_provider": "anthropic",
  "anthropic_api_key": "sk-ant-...",
  "anthropic_model": "claude-sonnet-4-6",
  "local_base_url": "http://127.0.0.1:8080",
  "local_model": "default",
  "local_context_window": 128000
}
```

The config file is auto-created with defaults on first access. Permissions: directory `0o700`, file `0o600` (owner-only). The `get_public_config()` function masks the API key for frontend display.

## Tool Loop (`shared/llm_tool_loop.py`)

`run_tool_loop()` is an async generator that drives the LLM conversation:

1. Stream LLM response, yielding text/thinking events to the client
2. If LLM requests tool calls, execute them
3. Feed results back to LLM and repeat
4. Stop when LLM produces a final text response (no tool calls)

### Three-Layer Context Budget

| Layer | Threshold | Purpose |
|-------|-----------|---------|
| **Token budget** | 80% of context window | Primary — prevents context overflow |
| **Character budget** | 500K cumulative tool result chars | Secondary — catches large results |
| **Call count** | 50 tool calls | Backstop — prevents infinite loops |

When any budget is exceeded, the loop emits a notification and stops.

### Write-Tool Approval Gate

Tools are classified as **read** or **write** in the tool registry. Read tools execute automatically. When the LLM requests a write tool:

1. Read tools in the same batch execute normally
2. The first write tool triggers a `tool_approval` SSE event
3. The stream pauses (returns `done` event)
4. Frontend displays the proposed action for user review
5. User approves or rejects via `POST /api/chat/tool-result`
6. The loop resumes with the decision

Per-tool-result truncation: each result is capped at 25K characters with boundary-aware JSON cutting.

## Tool Registry (`shared/tool_registry.py`)

20 tools sourced from MCP server implementations. Each tool has metadata flags:

| Flag | Purpose |
|------|---------|
| `readonly: true` | Executes without approval (default) |
| `readonly: false` | Requires user approval before execution |
| `translation_only: true` | Excluded by default; only included when caller passes `translation_only=True` |

Both general chat and translation endpoints pass `translation_only=True`, so `propose_verse_translation` is available in both contexts. The flag exists so that other future callers (e.g., a read-only query mode) can exclude it.

**Write tools** (require approval):
- `upsert_dictionary_entries`
- `update_grammar_category`
- `propose_verse_translation`

`get_tools()` accepts `readonly` and `translation_only` filters. `call_tool()` dispatches to the underlying MCP tool function.

## SSE Event Protocol

All streaming endpoints use Server-Sent Events. Each event is a JSON object on a `data:` line.

| Event Type | Source | Payload Fields | Description |
|---|---|---|---|
| `text` | llm_tool_loop | `content: string` | Text content chunk |
| `thinking_delta` | llm_provider | `content: string` | Incremental thinking text |
| `thinking_block` | llm_provider | `thinking: string, signature: string` | Complete thinking block (internal, not forwarded to frontend) |
| `tool_call` | llm_tool_loop | `name: string` | Tool execution starting (from `tool_use_start`) |
| `tool_use_start` | llm_provider | `id: string, name: string` | Raw tool use block started |
| `tool_input_delta` | llm_provider | `content: string` | Partial JSON input for tool |
| `tool_use` | llm_provider | `id: string, name: string, input: object` | Complete tool call (used internally) |
| `tool_result` | llm_tool_loop | `name: string, preview: string` | Tool result preview (first 500 chars) |
| `tool_approval` | llm_tool_loop | `call_id: string, tool_name: string, input: object` | Write tool awaiting user approval |
| `context_usage` | llm_tool_loop | `input_tokens: int, max_tokens: int` | Token usage after LLM response |
| `batch_system_prompt` | translate.py | `system: string, system_prompt_sig: string` | Batch system prompt + HMAC signature |
| `done` | llm_tool_loop | (empty) | Stream complete |
| `error` | llm_provider | `content: string` | Error occurred |
| `usage` | llm_provider | `input_tokens: int, output_tokens: int` | Final token usage stats |

## Batch Translation State Machine

Multi-verse translation uses a start/resume protocol:

```
1. Frontend: POST /translate-batch-stream
   Body: {verses: [...], language_name, book_name}

2. Backend emits: batch_system_prompt (with HMAC signature)
   Backend starts LLM tool loop

3. LLM gathers context (read tools execute automatically)
   LLM calls propose_verse_translation (write tool)

4. Backend emits: tool_approval {call_id, tool_name, input, messages_snapshot}
   Backend emits: done (stream pauses)

5. Frontend displays proposed translation for review
   User approves or rejects (with optional feedback)

6. Frontend: POST /translate-batch-resume
   Body: {messages (snapshot), system_prompt, system_prompt_sig,
          call_id, verse_number, decision, feedback?}

7. Backend verifies HMAC signature
   Backend injects decision + feedback into messages
   Backend resumes tool loop
   Repeat from step 3 for next verse
```

### HMAC Signing

The batch system prompt is signed with a per-process ephemeral key (`os.urandom(32)`). This prevents a client from modifying the system prompt between resume calls.

**Important**: The HMAC key is generated at process startup. If the FastAPI process restarts, all in-flight batch sessions become invalid (signature verification fails). This is by design — batch sessions should not survive process restarts.

### Message Snapshots

The `_messages_snapshot_gen()` wrapper intercepts `tool_approval` events from `run_tool_loop` and injects the full `messages` list as `messages_snapshot`. This allows the frontend to echo back the complete conversation state on resume without the backend persisting it (batch translation is stateless on the backend).

## Connection Models

Two MongoDB connection patterns coexist:

| Pattern | Location | Lifecycle | Used By |
|---------|----------|-----------|---------|
| `get_db()` | `routes/dependencies.py` | Per-request (connect/disconnect) | CRUD endpoints (bible_reader, dictionary, grammar, etc.) |
| `get_mongodb_connector()` | `db_connector/connection.py` | Global singleton | SSE streaming endpoints (chat, translate) |

**When to use which**: Use `get_db()` for simple request/response endpoints. Use `get_mongodb_connector()` for long-lived SSE streams that outlive a single HTTP request cycle — the singleton stays connected across multiple tool-loop iterations.

## Skills

Skill files live in `back_end/prompts/skills/`. Two patterns exist:

| Skill | Files | Discoverable | Injection |
|-------|-------|-------------|-----------|
| `generate-dictionary-entries` | `skill.json` + `SKILL.md` | Yes (via `GET /api/chat/skills`) | User-triggered |
| `translation-triologue` | `SKILL.md` only | No | Auto-injected when `chat_mode == "think_harder"` |

When `think_harder` mode is active, the triologue skill content is appended to the last user message before sending to the LLM (`routes/chat.py:102-126`).

## Key Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `shared/llm_tool_loop.py` | 329 | Shared streaming tool-use loop |
| `utils/llm_provider.py` | 185 | LLM provider abstraction (Anthropic + local) |
| `shared/tool_registry.py` | 610 | Tool definitions, dispatch, read/write classification |
| `shared/chat_config.py` | 104 | `~/.nlm/chat_config.json` management |
| `routes/chat.py` | 258 | Chat streaming + tool-result endpoints |
| `routes/translate.py` | 396 | Single + batch translation endpoints |
| `utils/chat_context.py` | — | Assembles MongoDB data context for system prompt |
| `shared/system_prompt.py` | — | Static system prompt for general chat |
