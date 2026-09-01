# Architecture Guide

## System Overview

The NLM Backend follows a layered architecture designed for async operations, secure credential management, and extensibility for LLM integration.

```
+------------------------------------------------------------------+
|                        CLIENT LAYER                               |
|  (Electron Frontend / External HTTP Clients)                      |
+------------------------------------------------------------------+
                              |
                              | HTTP/REST (no auth required)
                              v
+------------------------------------------------------------------+
|                     FASTAPI APPLICATION                           |
|  main.py                                                          |
|  +------------------------------------------------------------+  |
|  |  TrustedHostMiddleware (127.0.0.1 / localhost only)        |  |
|  +------------------------------------------------------------+  |
|  |  Request ID Middleware (request_id_middleware)              |  |
|  +------------------------------------------------------------+  |
|  |  Routes (see routes/ for the full list), including:         |  |
|  |  - /api/new-language        (POST)                          |  |
|  |  - /api/languages           (GET)                           |  |
|  |  - /api/bible-books         (GET)                           |  |
|  |  - /api/check-connection    (GET)                           |  |
|  |  - /api/import-bible        (POST)                          |  |
|  |  - /api/bible-reader        (GET)                           |  |
|  |  - /api/dictionary          (GET/POST/PATCH)                |  |
|  |  - /api/grammar             (GET/PATCH)                     |  |
|  |  - /api/chat                (POST)                          |  |
|  |  - /api/translate           (POST)                          |  |
|  |  - /api/word-index          (GET)                           |  |
|  |  - /api/correction-log      (GET/POST)                      |  |
|  |  - (and more)                                               |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                    DATABASE LAYER                                 |
|  db_connector/                                                    |
|  +------------------------------------------------------------+  |
|  |  MongoDBSettings (settings.py)                              |  |
|  |  - Two-tier credential loading                              |  |
|  |  - Connection pool configuration                            |  |
|  +------------------------------------------------------------+  |
|  |  MongoDBConnector (connection.py)                           |  |
|  |  - Async Motor client                                       |  |
|  |  - Per-request via get_db() for REST routes                 |  |
|  |  - Singleton via get_mongodb_connector() for MCP server     |  |
|  |  - Health check functionality                               |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                    MONGODB                                        |
|  Database: nlm_translator (default; set via DATABASE_NAME)        |
|  +------------------------------------------------------------+  |
|  |  Collections:                                               |  |
|  |  - languages          - bible_books                         |  |
|  |  - bible_texts        - base_structure_bible                |  |
|  |  - dictionaries       - grammar_systems                     |  |
|  |  - word_index         - correction_log                      |  |
|  |  - language_notes     - chat_conversations                  |  |
|  |  - phrase_index                                             |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
```

## Module Responsibilities

### main.py - Application Entry Point

**Responsibilities**:
- Initialize FastAPI application with metadata
- Register route handlers (see `routes/`) with `/api` prefix
- Attach two middleware layers for security and log tracing
- Start Uvicorn server on localhost:8221

**Note**: API authentication is disabled — see [api.md](./api.md#authentication).

**Key Components**:
```python
# Route registration — no auth dependency
app.include_router(new_language_router, prefix="/api")

# Middleware (LIFO execution order — TrustedHost runs outermost/first):
# 1. TrustedHostMiddleware: blocks requests not from 127.0.0.1 or localhost
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
# 2. request_id_middleware: attaches a short UUID to each request for log correlation
@app.middleware("http")
async def request_id_middleware(request: Request, call_next): ...

# Port read directly from OS environment — no .env file loaded
FAST_API_PORT = int(os.getenv('FAST_API_PORT', 8221))
```

### db_connector/ - Database Connection Layer

#### settings.py - Credential and Configuration Management

**Responsibilities**:
- Load credentials from `~/.nlm/mongodb_credentials.env`
- Validate MongoDB connection strings
- Configure connection pool settings
- Provide connection options for Motor client

**Credential Loading Flow**: reads `~/.nlm/mongodb_credentials.env` (external, never in repo — `MONGODB_CONNECTION_STRING` required, `DATABASE_NAME` optional) and builds a `MongoDBSettings` instance (`database_name` defaults to `"nlm_translator"`).

#### connection.py - MongoDB Connector

**Responsibilities**:
- Manage Motor async client lifecycle
- Provide database and collection access
- Implement health check functionality
- Support async context manager pattern

### routes/ - API Endpoint Handlers

#### new_language.py - Language Creation

**Responsibilities**:
- Validate language name input
- Create language metadata document
- Generate 66 Bible book structure documents (one per book)
- Initialize dictionary and grammar frameworks (one each)
- Create database indexes

**Data Flow for New Language Creation** (e.g. `language="Kope"`):
1. Validate input (alphanumeric) → normalize to `language_code = "kope"`
2. Create language metadata document
3. Create 66 Bible book documents (one per book)
4. Create dictionary framework (x1)
5. Create grammar system (x1)
6. Create indexes on `bible_texts`
7. Return success response with counts

### utils/ - Utility Modules

#### bible_generator/chapter_verse_numbers.py

**Purpose**: Provides static data for all 66 Bible books with accurate chapter and verse counts based on ESV (English Standard Version). See [database.md](./database.md#data-statistics) for the full book/chapter/verse breakdown.

**Data Structure**:
```python
BIBLE_CHAPTER_VERSES = {
    "Genesis": [(1, 31), (2, 25), ...],  # (chapter, verse_count) tuples
    "Exodus": [...],
    # ... all 66 books
}
```

#### bible_generator/bible_collection_manager.py

**Purpose**: Abstract base class defining the interface for Bible collection management.

**Abstract Methods** (subclasses must implement):
- `create_collection()` - Create the collection in the database
- `populate_collection()` - Populate the collection with data

**Concrete Helper Methods**:
- `create_bible_document()` - Create standardized document structure
- `create_bible_indexes()` - Set up efficient query indexes
- `get_collection_stats()` - Retrieve collection statistics

## Singleton MongoDB Connector

The global connector pattern ensures efficient connection reuse:

```python
# Global instance
_global_connector: Optional[MongoDBConnector] = None

async def get_mongodb_connector() -> MongoDBConnector:
    global _global_connector
    if _global_connector is None:
        _global_connector = MongoDBConnector()
        await _global_connector.connect()
    return _global_connector
```

**Note**: this singleton isn't the only connection pattern in use — see [chat-system.md](./chat-system.md#connection-models) for which pattern applies to which endpoint type.

## Security Architecture

### Authentication Status

API authentication is disabled — see [api.md](./api.md#authentication) for the full rationale.

### Security Measures

1. **Localhost Binding**: Server only binds to 127.0.0.1 (no external access)
2. **MongoDB Authentication**: Database operations use MongoDB's auth layer
3. **Credential Isolation**: Credentials stored in `~/.nlm/` outside the repository
4. **Input Validation**: Language names validated against regex pattern

## Error Handling Strategy

### HTTP Error Responses

| Status Code | Usage |
|------------|-------|
| 400 | Invalid input (e.g., bad language name) |
| 500 | Internal server error (database failures, etc.) |

See [development.md](./development.md#error-handling-pattern) for the exception-handling code convention.