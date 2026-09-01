# Developer Guide

## Setting Up Development Environment

### Prerequisites

- Python 3.10 or higher
- Local MongoDB 7.0+ (bundled `mongod` — see [configuration.md](./configuration.md#local-development-setup))

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd back_end
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv nlm_backend_venv

   # Linux/Mac
   source nlm_backend_venv/bin/activate

   # Windows
   nlm_backend_venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure credentials** — see [configuration.md](./configuration.md) for the credentials file format and local `mongod` setup.

5. **Verify setup**:
   ```bash
   python -c "from db_connector.settings import MongoDBSettings; print(MongoDBSettings.create_from_credentials())"
   ```

---

## Running the Application

### Development Server

```bash
# Standard startup
python main.py

# With hot reload
python -m uvicorn main:app --host 127.0.0.1 --port 8221 --reload

# With debug logging
LOG_LEVEL=DEBUG python main.py
```

### Accessing the API

Once running, the server is available at `http://localhost:8221`.

Swagger UI and ReDoc are disabled. See `back_end/docs/api.md` for the full endpoint reference.

**Test with curl**:
```bash
curl -X GET "http://localhost:8221/api/check-connection"
```

---

## Running Tests

### Test Suite Overview

The project uses pytest with the following test organization:

```
back_end/
|-- tests/
|   |-- conftest.py
|   |-- test_usfm_parser.py
|   |-- test_usfm_book_codes.py
|   |-- test_usfm_importer.py
|   |-- test_remove_usfm_markers.py
|   |-- unit/
|       |-- db_connector/
|           |-- conftest.py
|           |-- test_imports_and_structure.py
|           |-- test_mongodb_connection.py
|       |-- routes/
|       |-- chat/
|       |-- mcp_server/
|       |-- schema_enforcer/
|       |-- shared/
|           |-- test_model_registry.py
|           |-- test_system_prompt.py
|       |-- word_index/
|   |-- integration/
```

### Running Tests

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# With detailed logging (configured in pytest.ini)
pytest --log-cli-level=DEBUG

# Run specific test file
pytest tests/unit/db_connector/test_imports_and_structure.py

# Run specific test class
pytest tests/unit/db_connector/test_imports_and_structure.py::TestDbConnectorImports

# Run specific test function
pytest -k "test_mongodb_settings_class_structure"

# Run tests matching pattern
pytest -k "connection"

# Show test coverage (if pytest-cov installed)
pytest --cov=. --cov-report=html
```

### Test Configuration

`pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
asyncio_mode = auto
log_cli = true
log_level = DEBUG
log_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s
log_date_format = %Y-%m-%d %H:%M:%S
markers =
    integration: Tests requiring real filesystem resources (deselect with -m 'not integration')
```

### Running Connection Tests Directly

```bash
# Run all MongoDB connection tests
pytest tests/unit/db_connector/ -v

# Run specific connection test
pytest tests/unit/db_connector/test_mongodb_connection.py -v
```

---

## Code Patterns and Conventions

### Project Structure Conventions

| Directory | Purpose |
|-----------|---------|
| `routes/` | FastAPI route handlers |
| `shared/` | Core AI/chat infrastructure (tool loop, tool registry, chat config, model registry) |
| `db_connector/` | Database connection and settings |
| `utils/` | Utility modules and helpers |
| `mcp_server/` | MCP server for Claude tool access |
| `tests/` | Test files (prefixed with `test_`) |

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `new_language.py` |
| Classes | PascalCase | `MongoDBConnector` |
| Functions | snake_case | `create_new_language_mongodb` |
| Constants | UPPER_SNAKE_CASE | `LANGUAGES_COLLECTION` |
| Variables | snake_case | `language_code` |

### Async Patterns

All database operations should be async:

```python
# Good - async function
async def get_languages():
    connector = MongoDBConnector()
    await connector.connect()
    try:
        db = connector.get_database()
        languages = await db.languages.find().to_list(100)
        return languages
    finally:
        await connector.disconnect()

# Good - async context manager
async def get_languages():
    async with MongoDBConnector() as connector:
        db = connector.get_database()
        return await db.languages.find().to_list(100)
```

### Error Handling Pattern

```python
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

@router.post("/endpoint")
async def handler(data: str):
    # Validate input first
    if not is_valid(data):
        logger.warning(f"Invalid input: {data}")
        raise HTTPException(status_code=400, detail="Invalid input")

    connector = None
    try:
        connector = MongoDBConnector()
        await connector.connect()

        # Perform operations
        result = await do_work(connector, data)
        return {"success": True, "result": result}

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if connector:
            await connector.disconnect()
```

### Type Hints

Always use type hints for function signatures:

```python
from typing import Dict, List, Optional, Any

async def create_language(
    language_name: str,
    is_base: bool = False
) -> Dict[str, Any]:
    ...

def get_all_books() -> List[str]:
    ...

async def find_language(code: str) -> Optional[Dict[str, Any]]:
    ...
```

---

## Working with MongoDB

### Using MongoDBConnector

```python
from db_connector.connection import MongoDBConnector

# Method 1: Manual connection management
async def example_manual():
    connector = MongoDBConnector()
    await connector.connect()

    try:
        db = connector.get_database()
        collection = db["my_collection"]

        # Insert
        result = await collection.insert_one({"name": "test"})

        # Find
        doc = await collection.find_one({"_id": result.inserted_id})

        # Update
        await collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"name": "updated"}}
        )

        # Delete
        await collection.delete_one({"_id": result.inserted_id})

    finally:
        await connector.disconnect()

# Method 2: Context manager
async def example_context_manager():
    async with MongoDBConnector() as connector:
        db = connector.get_database()
        docs = await db.languages.find().to_list(100)
        return docs

# Method 3: Global singleton connector (used by MCP server, not REST routes)
# REST routes use Depends(get_db) from routes/dependencies.py instead.
from db_connector.connection import get_mongodb_connector

async def example_global():
    connector = await get_mongodb_connector()
    db = connector.get_database()
    return await db.languages.find().to_list(100)
```

---

## Debugging

### Enable Debug Logging

```python
# In your code
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via environment
LOG_LEVEL=DEBUG python main.py
```

### VS Code Launch Configuration

`.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI",
            "type": "debugpy",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "main:app",
                "--host", "127.0.0.1",
                "--port", "8221",
                "--reload"
            ],
            "cwd": "${workspaceFolder}/back_end",
            "env": {
                "PYTHONPATH": "${workspaceFolder}/back_end"
            }
        },
        {
            "name": "pytest",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["-v", "-s"],
            "cwd": "${workspaceFolder}/back_end"
        }
    ]
}
```

### Common Debug Commands

```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Test imports
python -c "from db_connector.connection import MongoDBConnector; print('OK')"

# Check environment variables
python -c "import os; print(os.environ.get('FAST_API_PORT', '8221 (default)'))"

# Test MongoDB connection
python -c "
import asyncio
from db_connector.connection import MongoDBConnector

async def test():
    c = MongoDBConnector()
    await c.connect()
    print('Connected:', c.is_connected)
    await c.disconnect()

asyncio.run(test())
"
```

---

## Pre-Commit Checklist

1. Run tests: `pytest`
2. Check types (if using mypy): `mypy .`
3. Format code (if using black): `black .`
4. Lint (if using flake8): `flake8 .`