# Developer Guide

## Setting Up Development Environment

### Prerequisites

- Python 3.10 or higher
- MongoDB Atlas account (or local MongoDB 7.0+)

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

4. **Configure credentials** (see [configuration.md](./configuration.md)):
   ```bash
   mkdir -p ~/.nlm
   echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27019"' > ~/.nlm/mongodb_credentials.env
   chmod 600 ~/.nlm/mongodb_credentials.env
   ```

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
|   |-- test_html_parser.py
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

## Adding New Routes

### Step-by-Step Guide

1. **Create route file** in `routes/`:
   ```python
   # routes/my_feature.py
   from fastapi import APIRouter, HTTPException
   from typing import Dict
   import logging

   router = APIRouter()
   logger = logging.getLogger('api')

   @router.get("/my-endpoint", response_model=Dict[str, str])
   async def my_endpoint():
       """
       Endpoint description.

       Returns:
           dict: Response data
       """
       return {"status": "ok"}
   ```

2. **Register in main.py**:
   ```python
   from routes.my_feature import router as my_feature_router

   app.include_router(my_feature_router, prefix="/api")
   ```

3. **Add tests**:
   ```python
   # tests/test_my_feature.py
   import pytest
   from fastapi.testclient import TestClient
   from main import app

   client = TestClient(app)

   def test_my_endpoint():
       response = client.get("/api/my-endpoint")
       assert response.status_code == 200
   ```

### Route Handler Template

```python
# routes/resource.py

from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, List, Optional
from pydantic import BaseModel
import logging
from datetime import datetime

from db_connector.connection import MongoDBConnector

router = APIRouter()
logger = logging.getLogger('api')

# Request/Response Models
class ResourceCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ResourceResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

# Routes
@router.post("/resources", response_model=ResourceResponse)
async def create_resource(data: ResourceCreate):
    """Create a new resource."""
    connector = None
    try:
        connector = MongoDBConnector()
        await connector.connect()
        db = connector.get_database()

        doc = {
            "name": data.name,
            "description": data.description,
            "created_at": datetime.utcnow()
        }

        result = await db.resources.insert_one(doc)

        return ResourceResponse(
            id=str(result.inserted_id),
            name=data.name,
            created_at=doc["created_at"]
        )

    except Exception as e:
        logger.error(f"Error creating resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if connector:
            await connector.disconnect()

@router.get("/resources/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str = Path(..., description="Resource ID")
):
    """Get a resource by ID."""
    # Implementation...
    pass

@router.get("/resources", response_model=List[ResourceResponse])
async def list_resources(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List all resources with pagination."""
    # Implementation...
    pass
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

### Common MongoDB Operations

```python
# Find with filter
docs = await collection.find({"status": "active"}).to_list(100)

# Find one
doc = await collection.find_one({"language_code": "kope"})

# Insert many
result = await collection.insert_many([
    {"name": "doc1"},
    {"name": "doc2"}
])

# Update many
result = await collection.update_many(
    {"status": "pending"},
    {"$set": {"status": "processed"}}
)

# Aggregation
pipeline = [
    {"$match": {"language_code": "kope"}},
    {"$group": {"_id": "$book_code", "count": {"$sum": 1}}}
]
async for doc in collection.aggregate(pipeline):
    print(doc)

# Create index
await collection.create_index([("language_code", 1), ("book_code", 1)])
```

---

## Writing Tests

### Test Structure

```python
# tests/test_feature.py

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

class TestMyFeature:
    """Tests for my feature."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.test_data = {"name": "test"}

    def test_synchronous_function(self):
        """Test a synchronous function."""
        result = my_sync_function("input")
        assert result == "expected"

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test an async function."""
        result = await my_async_function("input")
        assert result == "expected"

    @pytest.mark.parametrize("input,expected", [
        ("a", 1),
        ("b", 2),
        ("c", 3),
    ])
    def test_multiple_inputs(self, input, expected):
        """Test with multiple inputs."""
        assert my_function(input) == expected

# Fixtures
@pytest.fixture
def mock_connector():
    """Provide a mock MongoDB connector."""
    connector = Mock()
    connector.get_database = Mock(return_value=Mock())
    connector.is_connected = True
    return connector

@pytest.fixture
async def async_mock_connector():
    """Provide an async mock MongoDB connector."""
    connector = AsyncMock()
    connector.connect = AsyncMock()
    connector.disconnect = AsyncMock()
    return connector
```

### Mocking Database Calls

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mocked_db():
    # Mock the connector
    mock_db = AsyncMock()
    mock_db.languages.find_one = AsyncMock(return_value={
        "language_code": "kope",
        "status": "active"
    })

    with patch('routes.my_route.MongoDBConnector') as MockConnector:
        mock_instance = AsyncMock()
        mock_instance.get_database.return_value = mock_db
        mock_instance.connect = AsyncMock()
        mock_instance.disconnect = AsyncMock()
        MockConnector.return_value = mock_instance

        # Call your function
        result = await my_function("kope")

        # Assertions
        assert result["status"] == "active"
        mock_db.languages.find_one.assert_called_once()
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

## Git Workflow

### Branch Naming

```
feature/add-language-endpoint
bugfix/fix-connection-timeout
refactor/improve-error-handling
docs/update-api-reference
```

### Commit Messages

Follow conventional commits:

```
feat: add language creation endpoint
fix: resolve connection timeout issue
docs: update API documentation
refactor: improve error handling in routes
test: add tests for language repository
chore: update dependencies
```

### Pre-Commit Checklist

1. Run tests: `pytest`
2. Check types (if using mypy): `mypy .`
3. Format code (if using black): `black .`
4. Lint (if using flake8): `flake8 .`

---

## Useful Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Motor Documentation](https://motor.readthedocs.io/)
- [MongoDB Manual](https://www.mongodb.com/docs/manual/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)