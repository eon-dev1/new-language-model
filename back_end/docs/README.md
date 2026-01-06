# NLM Backend - FastAPI + MongoDB Bible Translation Platform

## Overview

The NLM (New Language Model) Backend is a FastAPI-based REST API that powers a Bible translation management platform. It provides services for managing multilingual Bible translations, dictionaries, and grammar systems with support for both human-curated and AI-generated content.

**Status**: MongoDB migration in progress (transitioning from PostgreSQL)

## Key Features

- **Dual-Level Translation Model**: Each non-English language supports both human and AI-generated versions of:
  - Bible texts
  - Dictionaries
  - Grammar systems
- **MongoDB Atlas Integration**: Async database operations via Motor driver
- **Localhost-Only Binding**: Server binds to 127.0.0.1 for security (no external network exposure)
- **Comprehensive Bible Structure**: Full 66-book Bible framework with accurate chapter/verse counts

**Note**: API authentication has been disabled for local development. MongoDB provides its own authentication layer.

## Quick Start

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
# FAST_API_KEY not required - authentication disabled for local development
```

3. Create `fastapi.env` in the backend root:
```env
CREDENTIALS_PATH="/path/to/your/credentials.env"
FAST_API_PORT=8221
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
pytest -k "test_settings_loading"
```

## Directory Structure

```
back_end/
|-- main.py                     # FastAPI application entry point
|-- pytest.ini                  # pytest configuration
|-- fastapi.env                 # Server configuration (port, credentials path)
|
|-- config/                     # Configuration classes
|   |-- mongodb.py              # MongoDB settings (local + Atlas support)
|   |-- atlas.py                # Atlas-specific settings with mem0 integration
|
|-- db_connector/               # Database connection layer
|   |-- connection.py           # MongoDBConnector class (Motor async driver)
|   |-- settings.py             # Two-tier credential loading system
|   |-- mongo_credentials_path.env  # Tier 1: path to actual credentials
|   |-- repositories/           # Data access layer (in development)
|
|-- routes/                     # API endpoint handlers
|   |-- new_language.py         # Language creation with dual-level support
|
|-- utils/                      # Utility modules
|   |-- bible_generator/        # Bible structure data and collection management
|   |   |-- chapter_verse_numbers.py  # Complete Bible chapter/verse data
|   |   |-- bible_collection_manager.py  # Abstract base for Bible repos
|   |-- grammar_generator/      # Grammar table generation (PostgreSQL legacy)
|   |-- usfm_parser/            # USFM Bible format parser and importer
|
|-- inference/                  # LLM service interfaces
|   |-- interfaces.py           # Abstract base classes for LLM integration
|
|-- tests/                      # Test suite
|   |-- unit/db_connector/      # MongoDB connection tests
|   |-- test_usfm_*.py          # USFM parser tests
```

## Core Concepts

### Dual-Level Translation Model

Non-English languages maintain parallel content sets:

| Content Type | Human Version | AI Version |
|-------------|---------------|------------|
| Bible Texts | Human-translated | LLM-generated |
| Dictionary | Human-curated | NLM-generated |
| Grammar System | Human-documented | NLM-generated |

English serves as the base language with only human-level content (no AI version).

### MongoDB Collections

- `languages` - Language metadata and translation progress
- `bible_books` - Book structure with chapters and verses
- `bible_texts` - Individual verse storage
- `dictionaries` - Word entries with definitions
- `grammar_systems` - Grammar rules by category

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
- [Database Schema](./database.md) - MongoDB collection schemas
- [Configuration Guide](./configuration.md) - Environment setup
- [Developer Guide](./development.md) - Development workflow

## Technology Stack

- **FastAPI 0.115.12** - Async web framework
- **Uvicorn 0.34.3** - ASGI server
- **Motor 3.x** - Async MongoDB driver
- **Pydantic** - Data validation and settings
- **pytest 8.4.1** - Testing framework

## Migration Status

| Component | Status |
|-----------|--------|
| MongoDB connection (Motor) | Complete |
| Two-tier credential system | Complete |
| Health monitoring | Complete |
| Language creation endpoint | Complete |
| Repository pattern | In Progress |
| Full CRUD operations | Pending |
| Data migration utilities | Pending |

## Local MongoDB Setup (Docker)

For development, we use a local MongoDB instance via Docker to avoid external dependencies.

### Quick Start

```bash
# Using docker-compose (recommended)
cd back_end/docker && docker compose up -d

# Or manually start MongoDB container on port 27018
docker run -d \
  --name nlm-mongodb \
  -p 27018:27017 \
  -v nlm-mongo-data:/data/db \
  mongo:8.0
```

**Port mapping**: `-p 27018:27017` maps container's MongoDB (27017) to host port 27018, avoiding conflicts with other MongoDB instances.

### Managing the Container

```bash
# Check status
docker ps --filter name=nlm-mongodb

# Stop
docker stop nlm-mongodb

# Start (after stopping)
docker start nlm-mongodb

# Remove (data persists in volume)
docker rm nlm-mongodb

# Remove data volume (CAUTION: deletes all data)
docker volume rm nlm-mongo-data
```

### Connection String

For local Docker MongoDB:
```
mongodb://localhost:27018
```

### Credentials Setup

1. Create credentials file:
```bash
mkdir -p ~/.nlm
echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27018"' > ~/.nlm/mongodb_credentials.env
```

2. Update `db_connector/mongo_credentials_path.env`:
```env
MONGODB_CREDENTIALS_PATH='/home/YOUR_USER/.nlm/mongodb_credentials.env'
DATABASE_NAME='nlm_db'
```

### Verify Connection

```bash
# Using mongosh (if installed)
mongosh --port 27018 --eval "db.runCommand({ping: 1})"

# Or via Docker
docker exec nlm-mongodb mongosh --eval "db.runCommand({ping: 1})"
```