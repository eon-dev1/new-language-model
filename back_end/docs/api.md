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
  "message": "Successfully created MongoDB collections and documents for language 'Kope' with dual-level support",
  "language_code": "kope",
  "is_base_language": "false",
  "translation_levels": ["human", "ai"],
  "documents_created": "137",
  "collections_touched": [
    "languages",
    "bible_books",
    "bible_texts",
    "dictionaries",
    "grammar_systems"
  ],
  "bible_books_count": "66",
  "bible_documents_created": "132",
  "dictionary_documents_created": "2",
  "grammar_documents_created": "2",
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
| translation_levels | array | Translation types created ("human", "ai") |
| documents_created | string | Total number of documents created |
| collections_touched | array | List of collections modified |
| bible_books_count | string | Number of Bible books (always 66) |
| bible_documents_created | string | Bible book documents (66 x translation_levels) |
| dictionary_documents_created | string | Dictionary framework documents |
| grammar_documents_created | string | Grammar system documents |
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
- **English special case**: Only creates "human" translation level (no AI version)
- **Indexes created**: Composite index on bible_texts for efficient queries

---

### GET /api/languages

Retrieve a list of all languages in the system.

**Note**: This endpoint is referenced in main.py but the route implementation may be pending migration to MongoDB.

#### Request

```bash
curl -X GET "http://localhost:8221/api/languages"
```

#### Expected Response

```json
{
  "languages": [
    {
      "language_name": "English",
      "language_code": "english",
      "is_base_language": true,
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "language_name": "Kope",
      "language_code": "kope",
      "is_base_language": false,
      "status": "active",
      "created_at": "2024-01-16T14:20:00Z"
    }
  ]
}
```

---

### GET /api/bible-books/{language}

Retrieve Bible book structure for a specific language.

**Note**: This endpoint is referenced in main.py but the route implementation may be pending migration to MongoDB.

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
  "translation_types": ["human", "ai"],
  "books": [
    {
      "book_name": "Genesis",
      "book_code": "genesis",
      "translation_type": "human",
      "total_chapters": 50,
      "total_verses": 1533,
      "translation_status": "not_started"
    },
    {
      "book_name": "Genesis",
      "book_code": "genesis",
      "translation_type": "ai",
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

**Note**: This endpoint is referenced in main.py but the route implementation may be pending migration to MongoDB.

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
  "collections_count": 5
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

When the server is running, access auto-generated documentation at:

- **Swagger UI**: http://localhost:8221/docs
- **ReDoc**: http://localhost:8221/redoc

These interfaces allow testing endpoints directly in the browser.

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