# Architecture Guide

## System Overview

The NLM Backend follows a layered architecture designed for async operations, secure credential management, and extensibility for LLM integration.

```
+------------------------------------------------------------------+
|                        CLIENT LAYER                               |
|  (Electron Frontend / External HTTP Clients)                      |
+------------------------------------------------------------------+
                              |
                              | HTTP/REST (Bearer Token Auth)
                              v
+------------------------------------------------------------------+
|                     FASTAPI APPLICATION                           |
|  main.py                                                          |
|  +------------------------------------------------------------+  |
|  |  Authentication Middleware (verify_api_key)                 |  |
|  +------------------------------------------------------------+  |
|  |  Routes:                                                    |  |
|  |  - /api/new-language     (POST)                            |  |
|  |  - /api/languages        (GET)                             |  |
|  |  - /api/bible-books      (GET)                             |  |
|  |  - /api/check-connection (GET)                             |  |
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
|  |  - Singleton pattern                                        |  |
|  |  - Health check functionality                               |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                    MONGODB ATLAS                                  |
|  Database: nlm_db                                         |
|  +------------------------------------------------------------+  |
|  |  Collections:                                               |  |
|  |  - languages                                                |  |
|  |  - bible_books                                              |  |
|  |  - bible_texts                                              |  |
|  |  - dictionaries                                             |  |
|  |  - grammar_systems                                          |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
```

## Module Responsibilities

### main.py - Application Entry Point

**Responsibilities**:
- Initialize FastAPI application with metadata
- Register route handlers with `/api` prefix
- Start Uvicorn server on localhost:8221

**Note**: API authentication has been disabled for local development. MongoDB provides its own authentication layer.

**Key Components**:
```python
# Route registration (no auth dependency for local development)
app.include_router(
    new_language_router,
    prefix="/api"
)
```

### db_connector/ - Database Connection Layer

#### settings.py - Credential and Configuration Management

**Responsibilities**:
- Implement two-tier credential loading
- Validate MongoDB connection strings
- Configure connection pool settings
- Provide connection options for Motor client

**Two-Tier Credential System Flow**:
```
+---------------------------+
| mongo_credentials_path.env |
| (Tier 1 - In Repository)   |
+---------------------------+
            |
            | Contains path to:
            v
+---------------------------+
| Actual Credentials File    |
| (Tier 2 - Secure Location) |
+---------------------------+
            |
            | Contains:
            | - MONGODB_CONNECTION_STRING
            | - FAST_API_KEY
            v
+---------------------------+
| MongoDBSettings Instance   |
+---------------------------+
```

#### connection.py - MongoDB Connector

**Responsibilities**:
- Manage Motor async client lifecycle
- Provide database and collection access
- Implement health check functionality
- Support async context manager pattern

**Connection State Machine**:
```
    +-------------+
    | INITIALIZED |
    +-------------+
          |
          | connect()
          v
    +-------------+
    | CONNECTING  |
    +-------------+
          |
          | ping successful
          v
    +-------------+
    | CONNECTED   |<----+
    +-------------+     |
          |             |
          | disconnect()|  reconnect via
          v             |  ensure_connected()
    +--------------+    |
    | DISCONNECTED |----+
    +--------------+
```

### routes/ - API Endpoint Handlers

#### new_language.py - Language Creation

**Responsibilities**:
- Validate language name input
- Create language metadata document
- Generate Bible book structures (human + AI versions)
- Initialize dictionary and grammar frameworks
- Create database indexes

**Data Flow for New Language Creation**:
```
Input: language="Kope"
          |
          v
    +------------------+
    | Validate Input   |
    | (alphanumeric)   |
    +------------------+
          |
          | language_code = "kope"
          v
    +------------------+
    | Create Language  |
    | Metadata         |
    +------------------+
          |
          v
    +------------------+
    | Create 66 Books  |
    | (Human + AI)     |
    | = 132 documents  |
    +------------------+
          |
          v
    +------------------+
    | Create Dictionary|
    | Framework (x2)   |
    +------------------+
          |
          v
    +------------------+
    | Create Grammar   |
    | System (x2)      |
    +------------------+
          |
          v
    +------------------+
    | Create Indexes   |
    | on bible_texts   |
    +------------------+
          |
          v
Output: Success response with counts
```

### utils/ - Utility Modules

#### bible_generator/chapter_verse_numbers.py

**Purpose**: Provides static data for all 66 Bible books with accurate chapter and verse counts based on ESV (English Standard Version).

**Data Structure**:
```python
BIBLE_CHAPTER_VERSES = {
    "Genesis": [(1, 31), (2, 25), ...],  # (chapter, verse_count) tuples
    "Exodus": [...],
    # ... all 66 books
}
```

**Statistics**:
- 39 Old Testament books
- 27 New Testament books
- 1,189 total chapters
- 31,102 total verses

#### bible_generator/bible_collection_manager.py

**Purpose**: Abstract base class defining the interface for Bible collection management.

**Key Methods**:
- `create_bible_document()` - Create standardized document structure
- `create_bible_indexes()` - Set up efficient query indexes
- `get_collection_stats()` - Retrieve collection statistics

### inference/ - LLM Service Interfaces

**Purpose**: Define abstract interfaces for LLM provider integration.

**Key Abstractions**:
- `LLMService` - Core service interface for translation and analysis
- `LLMProvider` - Provider implementation base class
- `ProviderFactory` - Protocol for creating provider instances

## Async Patterns

### Motor Async Driver Usage

All database operations use Python's async/await pattern with the Motor driver:

```python
# Connection
async def connect(self) -> None:
    self._client = AsyncIOMotorClient(connection_string, **options)
    await self._client.admin.command('ping')

# Database operations
async def create_document(self, collection_name: str, document: dict):
    collection = self._database[collection_name]
    result = await collection.insert_one(document)
    return result.inserted_id
```

### FastAPI Async Endpoints

All route handlers are async to maximize concurrency:

```python
@router.post("/new-language", response_model=Dict[str, str])
async def create_new_language_mongodb(language: str):
    connector = MongoDBConnector()
    await connector.connect()
    # ... async operations
    await connector.disconnect()
```

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

**Note**: Currently, the `new_language.py` route creates its own connector instance per request. Migration to the global singleton is recommended for production.

## Security Architecture

### Authentication Status

**API authentication has been disabled for local development.** The server relies on:
- MongoDB's own authentication layer for database access
- Localhost-only binding (127.0.0.1) preventing external access

```
Client Request
      |
      | No authentication required
      v
+------------------+
| Route Handler    |
+------------------+
      |
      v
+------------------+
| MongoDBConnector |
| (uses MongoDB    |
|  credentials)    |
+------------------+
```

### Security Measures

1. **Localhost Binding**: Server only binds to 127.0.0.1 (no external access)
2. **MongoDB Authentication**: Database operations use MongoDB's auth layer
3. **Credential Isolation**: Two-tier system keeps secrets out of repository
4. **Input Validation**: Language names validated against regex pattern

## Configuration Flow

```
+-------------------+     +----------------------+
| fastapi.env       | --> | Environment          |
| CREDENTIALS_PATH  |     | Variables Loaded     |
| FAST_API_PORT     |     +----------------------+
+-------------------+              |
                                   v
+-------------------+     +----------------------+
| mongo_credentials |     | MongoDBSettings      |
| _path.env         | --> | Two-tier Loading     |
| - PATH            |     | - Connection String  |
| - DATABASE_NAME   |     | - Database Name      |
+-------------------+     +----------------------+
        |                          |
        v                          v
+-------------------+     +----------------------+
| Actual Credentials|     | MongoDBConnector     |
| File (external)   |     | Initialized          |
| - CONNECTION_STR  |     +----------------------+
| - FAST_API_KEY    |
+-------------------+
```

## Error Handling Strategy

### HTTP Error Responses

| Status Code | Usage |
|------------|-------|
| 400 | Invalid input (e.g., bad language name) |
| 401 | Invalid or missing API key |
| 500 | Internal server error (database failures, etc.) |

### Exception Handling Pattern

```python
try:
    connector = MongoDBConnector()
    await connector.connect()
    # ... operations
except HTTPException:
    raise  # Re-raise HTTP exceptions
except Exception as e:
    logger.error(f"Error: {e}")
    raise HTTPException(status_code=500, detail=str(e))
finally:
    if connector:
        await connector.disconnect()
```

## Future Architecture Considerations

1. **Connection Pooling Optimization**: Tune pool sizes based on load patterns
2. **Caching Layer**: Add Redis for frequently accessed data
3. **Background Tasks**: Use FastAPI BackgroundTasks for async processing
4. **Rate Limiting**: Implement request throttling
5. **Metrics Collection**: Add Prometheus/OpenTelemetry integration