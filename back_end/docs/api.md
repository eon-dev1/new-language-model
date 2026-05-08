# API Reference

## Base URL

```
http://localhost:8221/api
```

The server binds to localhost only and is not accessible from external networks.

## Authentication

**Authentication has been disabled for local development.**

The API runs without Bearer token authentication for the following reasons:
- MongoDB provides its own authentication layer
- The server binds to localhost only (127.0.0.1), preventing external access
- Simplifies local development workflow

### Example with curl

```bash
curl -X GET "http://localhost:8221/api/languages"
```

### Example with Python requests

```python
import requests

response = requests.get("http://localhost:8221/api/languages")
```

---

## Endpoints

### POST /api/new-language

Create a new language dataset with all required collections and documents for Bible translation work.

#### Request

**Content-Type**: `application/json` or query parameter

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| language | string | Yes | Language name (e.g., "Kope", "Swahili") |

**Validation Rules**:
- Alphanumeric characters only
- Spaces, hyphens, and underscores allowed
- Pattern: `^[a-zA-Z0-9_ -]+$`

#### Request Examples

Query parameter:
```bash
curl -X POST "http://localhost:8221/api/new-language?language=Kope"
```

JSON body:
```bash
curl -X POST "http://localhost:8221/api/new-language" \
  -H "Content-Type: application/json" \
  -d '{"language": "Kope"}'
```

#### Response

**Success (200 OK)**:

```json
{
  "success": "true",
  "message": "Successfully created MongoDB collections and documents for language 'Kope'",
  "language_code": "kope",
  "is_base_language": "false",
  "documents_created": "69",
  "collections_touched": "['languages', 'bible_books', 'bible_texts', 'dictionaries', 'grammar_systems']",
  "bible_books_count": "66",
  "total_verses_framework": "31102"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| success | string | "true" on success |
| message | string | Human-readable success message |
| language_code | string | Normalized language code (lowercase, underscores) |
| is_base_language | string | "true" if English, "false" otherwise |
| documents_created | string | Total number of documents created |
| collections_touched | string | Python-formatted string list of collections modified |
| bible_books_count | string | Number of Bible books (always 66) |
| total_verses_framework | string | Total verse count (31,102) |

#### Error Responses

**Invalid Language Name (400)**:
```json
{
  "detail": "Invalid language name. Use alphanumeric, spaces, hyphens, or underscores only."
}
```

**Internal Error (500)**:
```json
{
  "detail": "Error message describing the failure"
}
```

#### Behavior Notes

- **Idempotent for metadata**: If language already exists, updates `updated_at` and `status`
- **Non-duplicating**: Skips existing Bible books, dictionaries, and grammar systems
- **Single document per entity**: One bible_books doc per book, one dictionary, one grammar system per language
- **Indexes created**: Composite index on bible_texts for efficient queries

---

### GET /api/languages

Retrieve a list of all languages in the system with live verification progress.

#### Request

```bash
curl -X GET "http://localhost:8221/api/languages"
```

#### Response

```json
{
  "languages": [
    {
      "language_code": "english",
      "language_name": "English",
      "total_verses": 31102,
      "verified_count": 0,
      "verification_progress": {
        "old_testament": 0.0,
        "new_testament": 0.0,
        "total": 0.0
      },
      "status": "active",
      "is_base_language": true
    },
    {
      "language_code": "kope",
      "language_name": "Kope",
      "total_verses": 7957,
      "verified_count": 42,
      "verification_progress": {
        "old_testament": 0.0,
        "new_testament": 17.6,
        "total": 0.53
      },
      "status": "active",
      "is_base_language": false
    }
  ]
}
```

---

### GET /api/bible-books/{language}

Retrieve Bible book structure for a specific language.

#### Request

```bash
curl -X GET "http://localhost:8221/api/bible-books/kope"
```

#### Path Parameters

| Name | Type | Description |
|------|------|-------------|
| language | string | Language code (e.g., "kope", "english") |

#### Expected Response

```json
{
  "language_code": "kope",
  "books": [
    {
      "book_name": "Genesis",
      "book_code": "genesis",
      "total_chapters": 50,
      "total_verses": 1533,
      "translation_status": "not_started"
    }
  ]
}
```

---

### GET /api/check-connection

Health check endpoint to verify database connectivity.

#### Request

```bash
curl -X GET "http://localhost:8221/api/check-connection"
```

#### Expected Response

**Success**:
```json
{
  "status": "healthy",
  "database": "nlm_db",
  "connected": true,
  "ping_success": true,
  "server_info": {
    "version": "7.0.0",
    "platform": "MongoDB Atlas"
  },
  "collections_count": 9
}
```

**Failure**:
```json
{
  "status": "unhealthy",
  "connected": false,
  "error": "Connection timeout"
}
```

---

### Bible Reader Endpoints

#### GET /api/verses/{language}/{book_code}/{chapter}

Get all verses for a chapter.

**Response**: `{language_code, book_code, chapter, verses: [{verse, english_text, translated_text, human_verified}], count}`

#### PUT /api/verses/{language}/{book_code}/{chapter}/{verse}

Update verse translated text. Triggers async word index rebuild for the language.

**Body**: `{translated_text: string}`

**Response**: `{success, language_code, book_code, chapter, verse, translated_text, human_verified}`

#### PATCH /api/verses/{language}/{book_code}/{chapter}/{verse}/verify

Toggle human verification status on a verse.

**Body**: `{human_verified: boolean}`

**Response**: `{success, language_code, book_code, chapter, verse, human_verified}`

#### GET /api/verses/{language}/search

Search verse text. Query params: `q` (required, 2-200 chars), `limit` (default 50).

**Response**: `{results: [{book_code, chapter, verse, english_text, translated_text}], count, query}`

---

### Dictionary Endpoints

#### GET /api/dictionary/{language}/entries

Paginated dictionary entries. Query params: `offset`, `limit`, `search`.

#### POST /api/dictionary/{language}/entries

Create a dictionary entry.

#### PATCH /api/dictionary/{language}/entries/{word}/verify

Toggle human verification on a dictionary entry.

---

### Grammar Endpoints

#### GET /api/grammar/{language}/categories

List all 5 grammar categories with content status.

#### POST /api/grammar/{language}/categories/{category_name}

Update grammar category content.

#### PATCH /api/grammar/{language}/categories/{category_name}/verify

Toggle human verification on a grammar category.

---

### Chat Endpoints

See [chat-system.md](./chat-system.md) for the full SSE event protocol and architecture.

#### POST /api/chat/stream

Stream a chat response with tool-use support via SSE.

**Body**:
```json
{
  "messages": [{"role": "user", "content": "..."}],
  "context": {"language_code": "kope", "book_code": "genesis", "chapter": 1, "view": "bible"},
  "conversation_id": "optional-id",
  "thinking_enabled": false,
  "chat_mode": null
}
```

`chat_mode` options: `null`, `"think"`, `"think_harder"`, `"maximum_thinking"`, `"deep_research"`.

**Response**: SSE stream (see [chat-system.md](./chat-system.md) for event types).

#### POST /api/chat/tool-result

Resume a paused chat stream after user approves/rejects a write tool.

**Body**: `{conversation_id, call_id, decision: "approve"|"reject", modified_input?: object}`

**Response**: SSE stream continuing the conversation.

#### GET /api/chat/config

Get current LLM configuration (API key masked).

**Response**: `{llm_provider, anthropic_model, has_api_key, api_key_preview, has_openrouter_key, openrouter_key_preview, openrouter_model, local_base_url, local_model, local_context_window, thinking_enabled}`

#### POST /api/chat/config

Update LLM configuration.

**Body**: `{llm_provider?, anthropic_api_key?, anthropic_model?, openrouter_api_key?, openrouter_model?, local_base_url?, local_model?, thinking_enabled?}`

#### POST /api/chat/test-connection

Test connection to the configured LLM provider.

**Response**: `{success: boolean, error?: string}`

#### GET /api/chat/conversations

List all conversations, newest first (max 100).

**Response**: `[{id, title, created_at, updated_at, message_count}]`

#### POST /api/chat/conversations

Create a new conversation.

**Body**: `{title?: string}`

**Response**: `{id: string}`

#### GET /api/chat/conversations/{conversation_id}

Get conversation with full message history.

**Response**: `{id, title, messages: [{role, content, timestamp, tool_calls?, thinking_content?}], created_at, updated_at}`

#### DELETE /api/chat/conversations/{conversation_id}

Delete a conversation. Returns `{deleted: true}`.

#### PATCH /api/chat/conversations/{conversation_id}/title

Update conversation title.

**Body**: `{title: string}`

#### GET /api/chat/skills

List discoverable skills (those with `skill.json` metadata).

**Response**: `[{key, label, views, prompt}]`

---

### Translation Endpoints

See [chat-system.md](./chat-system.md) for the batch translation state machine and HMAC signing.

#### POST /api/verses/{language}/{book_code}/{chapter}/{verse}/translate-stream

Single verse translation via SSE. Uses the shared tool loop with translation-focused tools.

**Body**: `{english_text, language_name, book_name}`

**Response**: SSE stream.

#### POST /api/verses/{language}/{book_code}/{chapter}/translate-batch-stream

Start a multi-verse batch translation session.

**Body**:
```json
{
  "verses": [{"verse_number": 1, "english_text": "..."}, ...],
  "language_name": "Bughotu",
  "book_name": "John"
}
```

**Response**: SSE stream. First event is `batch_system_prompt` with HMAC signature.

#### POST /api/verses/{language}/{book_code}/{chapter}/translate-batch-resume

Resume a batch session after approving/rejecting a verse proposal.

**Body**:
```json
{
  "messages": [...],
  "system_prompt": "...",
  "system_prompt_sig": "hmac-hex",
  "call_id": "tool-use-id",
  "verse_number": 1,
  "decision": "approve",
  "feedback": null
}
```

**Response**: SSE stream continuing the batch.

---

### Import Endpoints

#### POST /api/import-bible

Import USFM Bible files. See [import.md](./import.md) for details.

#### POST /api/import-html-bible

Import HTML Bible files. See [import.md](./import.md) for details.

---

### Export Endpoint

#### POST /api/export-usfm

Export a language's translations to USFM files.

**Body**: `{language_code: string, output_dir: string}`

**Response**: `{success, files_written, message}`

---

### Database Backup

#### POST /api/backup-database

Create a timestamped gzipped BSON backup using `mongodump`.

**Body**: `{output_dir: string}`

**Response**: `{success, backup_dir, message, duration_ms}`

---

### Word Index

#### POST /api/word-index/rebuild

Rebuild the word frequency index for a language.

**Body**: `{language_code: string}`

**Response**: `{success, language_code, words_indexed}`

---

### Memories (Language Notes)

#### GET /api/memories/{language}/notes

List all notes for a language, sorted by recency.

**Response**: `{language_code, notes: [{id, text, created_at, updated_at}], count}`

#### POST /api/memories/{language}/notes

Create a note. **Body**: `{text: string}`

#### PUT /api/memories/{language}/notes/{note_id}

Update a note. **Body**: `{text: string}`

#### DELETE /api/memories/{language}/notes/{note_id}

Delete a note.

---

### Correction Log

#### POST /api/correction-log/{language}

Log a correction (status 201).

**Body**: `{content_type: "bible_verse"|"dictionary_entry"|"grammar_category", content_reference: object, original_text, what_was_wrong, correction}`

#### GET /api/correction-log/{language}

List correction log entries. Query params: `content_type?`, `page` (default 1), `page_size` (default 20).

**Response**: `{language_code, entries: [{id, content_type, content_reference, original_text, what_was_wrong, correction, created_at}], total, page, page_size}`

#### PUT /api/correction-log/{language}/{log_id}

Update the `what_was_wrong` field. **Body**: `{what_was_wrong: string}`

---

### Other Endpoints

#### POST /api/load-base-language

Ensure the English base language and Bible structure exists.

---

## Error Codes Reference

| Code | Status | Description |
|------|--------|-------------|
| 400 | Bad Request | Invalid input data or parameters |
| 404 | Not Found | Resource does not exist |
| 500 | Internal Server Error | Database or server error |

## Common Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. The server relies on localhost-only binding for access control. MongoDB provides its own authentication for database operations.

## CORS

CORS is not configured by default since the API is designed for localhost access. If cross-origin access is needed, configure FastAPI middleware:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Interactive Documentation

Swagger UI and ReDoc are disabled (`docs_url=None, redoc_url=None, openapi_url=None` in `main.py`). Use this document or direct `curl`/`httpie` calls to explore the API.

## Code Examples

### Python - Create New Language

```python
import requests

BASE_URL = "http://localhost:8221/api"

# Create a new language
response = requests.post(
    f"{BASE_URL}/new-language",
    params={"language": "Swahili"}
)

if response.status_code == 200:
    data = response.json()
    print(f"Created language: {data['language_code']}")
    print(f"Documents created: {data['documents_created']}")
else:
    print(f"Error: {response.json()['detail']}")
```

### JavaScript/Node.js - Fetch Languages

```javascript
const fetch = require('node-fetch');

const BASE_URL = 'http://localhost:8221/api';

async function getLanguages() {
  const response = await fetch(`${BASE_URL}/languages`);

  if (response.ok) {
    const data = await response.json();
    console.log('Languages:', data.languages);
  } else {
    const error = await response.json();
    console.error('Error:', error.detail);
  }
}

getLanguages();
```

### Async Python with httpx

```python
import httpx
import asyncio

BASE_URL = "http://localhost:8221/api"

async def check_connection():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/check-connection")
        return response.json()

# Run
result = asyncio.run(check_connection())
print(f"Status: {result['status']}")
```