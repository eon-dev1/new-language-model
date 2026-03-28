# NLM Backend - FastAPI + MongoDB Bible Translation Platform

## Overview

The NLM (New Language Model) Backend is a FastAPI-based REST API that powers a Bible translation management platform. It provides services for managing multilingual Bible translations, dictionaries, and grammar systems with support for both human-curated and AI-generated content.

**Status**: Active development (MongoDB backend)

## Key Features

- **Single-Document Model**: Each entity (verse, dictionary, grammar system, bible book) has one document per language. Verification status is tracked via `human_verified: bool` rather than separate document sets.
- **MongoDB Integration**: Async database operations via Motor driver
- **Localhost-Only Binding**: Server binds to 127.0.0.1 for security (no external network exposure)
- **Comprehensive Bible Structure**: Full 66-book Bible framework with accurate chapter/verse counts

**Note**: API authentication has been disabled for local development. MongoDB provides its own authentication layer.

## Quick Start

## Start server 
~/.nlm/bin/mongod --port 27019 --dbpath ~/.nlm/db

### Prerequisites

- Python 3.12+
- MongoDB Atlas account (or local MongoDB instance)
- Virtual environment

### Installation

```bash
cd back_end

# Create and activate virtual environment
python -m venv nlm_backend_venv
source nlm_backend_venv/bin/activate  # Linux/Mac
# OR
nlm_backend_venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Create `db_connector/mongo_credentials_path.env`:
```env
MONGODB_CREDENTIALS_PATH="/path/to/your/credentials.env"
DATABASE_NAME="nlm_db"
```

2. Create your credentials file at the path specified above:
```env
MONGODB_CONNECTION_STRING="mongodb+srv://user:password@cluster.mongodb.net/"
```

### Running the Server

```bash
# Standard startup
python main.py

# With hot reload (development)
python -m uvicorn main:app --host 127.0.0.1 --port 8221 --reload
```

The server binds to `localhost:8221` only (not exposed to external networks).

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/db_connector/test_mongodb_connection.py

# Run specific test by name
pytest -k "test_settings_creation_succeeds"
```

## Directory Structure

```
back_end/
|-- main.py                     # FastAPI application entry point
|-- pytest.ini                  # pytest configuration
|-- requirements.txt            # Python dependencies
|
|-- db_connector/               # Database connection layer
|   |-- connection.py           # MongoDBConnector class (Motor async driver)
|   |-- settings.py             # Two-tier credential loading system
|   |-- mongo_credentials_path.env  # Tier 1: path to actual credentials
|
|-- routes/                     # API endpoint handlers (20 route modules)
|   |-- dependencies.py         # Shared get_db() dependency injection
|   |-- new_language.py         # Language creation
|   |-- languages.py            # Language listing
|   |-- bible_books.py          # Bible book structure
|   |-- check_connection.py     # Health check
|   |-- import_bible.py         # USFM import
|   |-- import_html_bible.py    # HTML import
|   |-- ...                     # (and more)
|
|-- mcp_server/                 # MCP server for Claude tool access
|
|-- utils/                      # Utility modules
|   |-- bible_generator/        # Bible structure data and collection management
|   |   |-- chapter_verse_numbers.py  # Complete Bible chapter/verse data
|   |   |-- bible_collection_manager.py  # Abstract base for Bible collection managers
|   |-- usfm_parser/            # USFM Bible format parser and importer
|   |-- html_parser/            # HTML Bible format parser and importer
|   |-- schema_enforcer/        # MongoDB schema validation
|   |-- word_index/             # Word frequency tracking
|
|-- tests/                      # Test suite
|   |-- unit/db_connector/      # MongoDB connection tests
|   |-- unit/routes/            # Route handler tests
|   |-- unit/mcp_server/        # MCP server tests
|   |-- integration/            # Integration tests
|   |-- test_usfm_parser.py     # USFM parser tests
|   |-- test_html_parser.py     # HTML parser tests
```

## Core Concepts

### Single-Document Model

Each language has one document per entity — one dictionary, one grammar system, 66 bible_books documents (one per book). Verification state is tracked with `human_verified: bool` on individual items (verses, dictionary entries, grammar categories). There is no separate "human" vs "AI" document set.

English is the base language (`is_base_language: true`). Its verses use `english_text`; all other languages use `translated_text`.

### MongoDB Collections

- `languages` - Language metadata and translation progress
- `base_structure_bible` - Canonical Bible structure (generator scripts)
- `bible_books` - Book structure with chapters and verses
- `bible_texts` - Individual verse storage
- `dictionaries` - Word entries with definitions
- `grammar_systems` - Grammar rules by category
- `word_index` - Word frequency and dictionary gap tracking
- `language_notes` - Per-language notes and observations
- `correction_log` - Edit history for translations, dictionary, grammar
- `chat_conversations` - AI chat conversation history

### Authentication

API authentication has been disabled for local development:
- MongoDB provides its own authentication layer
- Server binds to localhost only (127.0.0.1)
- No Bearer token required

```bash
curl http://localhost:8221/api/languages
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/new-language` | Create new language with all collections |
| GET | `/api/languages` | List all languages |
| GET | `/api/bible-books/{language}` | Get Bible structure for language |
| GET | `/api/check-connection` | Health check |

See [api.md](./api.md) for detailed API documentation.

## Related Documentation

- [Architecture Guide](./architecture.md) - System design and patterns
- [API Reference](./api.md) - Complete endpoint documentation
- [Chat & AI System](./chat-system.md) - LLM integration, tool loop, SSE protocol, batch translation
- [Database Schema](./database.md) - MongoDB collection schemas
- [Configuration Guide](./configuration.md) - Environment setup
- [Developer Guide](./development.md) - Development workflow

## Technology Stack

- **FastAPI** >=0.115 - Async web framework
- **Uvicorn** >=0.30 - ASGI server
- **Motor** >=3.0 - Async MongoDB driver
- **Pydantic** >=2.0 - Data validation and settings
- **pytest** >=8.0 - Testing framework

## Migration Status

The MongoDB migration from the original PostgreSQL prototype is complete.

## Local MongoDB Setup

MongoDB is downloaded to `~/.nlm/bin/mongod` (by `npm run prepare:mongo`) and is managed automatically when running the full app.

When running the backend standalone (`python main.py` outside Electron), start MongoDB manually first:

```bash
~/.nlm/bin/mongod --port 27019 --dbpath ~/.nlm/db
```

### Credentials Setup

1. Create credentials file:
```bash
mkdir -p ~/.nlm
echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27019"' > ~/.nlm/mongodb_credentials.env
```

2. Update `db_connector/mongo_credentials_path.env`:
```env
MONGODB_CREDENTIALS_PATH='/home/YOUR_USER/.nlm/mongodb_credentials.env'
DATABASE_NAME='nlm_db'
```

### Verify Connection

```bash
mongosh --port 27019 --eval "db.runCommand({ping: 1})"
```