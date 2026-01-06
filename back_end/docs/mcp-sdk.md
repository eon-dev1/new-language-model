# Model Context Protocol (MCP) Python SDK - Reference Documentation

## 1. Installation

### Package Name
The official package is **`mcp`** on PyPI.

### Installation Commands

```bash
# Using pip (standard)
pip install "mcp[cli]"

# Using uv (recommended by Anthropic)
uv add "mcp[cli]"

# With HTTP client support
pip install "mcp[cli]" httpx
```

**Requirements:**
- Python 3.10+
- MCP SDK version 1.2.0 or higher

---

## 2. Server Setup

### Basic Server Creation

```python
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server with a name
mcp = FastMCP("my-server-name")

# Run the server with stdio transport (for Claude Code integration)
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Server with Configuration Options

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="mongodb-tools",
    json_response=True,           # Return JSON-formatted responses
    mask_error_details=True       # Hide internal error details from clients
)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Available Transport Types

- **`stdio`** - Standard input/output (recommended for Claude Code)
- **`streamable-http`** - HTTP with streaming support
- **`sse`** - Server-Sent Events (deprecated)

---

## 3. Tool Registration

### Basic Tool Registration

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number
    """
    return a + b
```

### Async Tool Registration

```python
@mcp.tool()
async def fetch_data(url: str) -> str:
    """Fetch data from a URL."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

### Custom Tool Metadata

```python
@mcp.tool(
    name="search_database",
    description="Search the MongoDB database with a query",
    tags={"database", "search"},
    meta={"version": "1.0", "author": "your-team"}
)
def search_db_implementation(query: str, limit: int = 10):
    """Implementation function."""
    pass
```

---

## 4. Tool Schema Format - Input Parameters and Types

### Basic Type Hints

```python
@mcp.tool()
def example_tool(
    name: str,              # Required string
    count: int,             # Required integer
    price: float,           # Required float
    active: bool,           # Required boolean
    items: list[str],       # List of strings
    metadata: dict[str, int] # Dictionary
) -> str:
    """Tool with various parameter types."""
    pass
```

### Optional Parameters with Defaults

```python
@mcp.tool()
def search_documents(
    query: str,                      # Required
    limit: int = 10,                 # Optional with default
    skip: int = 0,                   # Optional with default
    collection: str | None = None,   # Optional, accepts None
    sort_order: str = "asc"          # Optional with default
) -> list[dict]:
    """Search documents with optional parameters."""
    pass
```

### Using Annotated for Descriptions

```python
from typing import Annotated

@mcp.tool()
def insert_document(
    collection: Annotated[str, "Name of the MongoDB collection"],
    document: Annotated[dict, "The document to insert as a dictionary"],
    upsert: Annotated[bool, "Whether to update if document exists"] = False
) -> str:
    """Insert a document into MongoDB."""
    pass
```

### Using Pydantic Field for Validation

```python
from typing import Annotated, Literal
from pydantic import Field

@mcp.tool()
def query_database(
    collection: Annotated[str, Field(description="Collection name", min_length=1)],
    limit: Annotated[int, Field(description="Max results", ge=1, le=1000)] = 100,
    sort_field: Annotated[str | None, Field(description="Field to sort by")] = None,
    sort_order: Annotated[Literal["asc", "desc"], Field(description="Sort direction")] = "asc"
) -> list[dict]:
    """Query the database with validated parameters."""
    pass
```

### Using Pydantic Models for Complex Parameters

```python
from pydantic import BaseModel, Field
from typing import Optional

class MongoQuery(BaseModel):
    """Schema for MongoDB query parameters."""
    collection: str = Field(description="Collection name")
    filter: dict = Field(default={}, description="MongoDB filter query")
    projection: Optional[dict] = Field(default=None, description="Fields to include/exclude")
    limit: int = Field(default=10, ge=1, le=1000, description="Maximum documents to return")
    skip: int = Field(default=0, ge=0, description="Number of documents to skip")

@mcp.tool()
def advanced_query(query: MongoQuery) -> list[dict]:
    """Execute an advanced MongoDB query."""
    pass
```

### Supported Type Annotations

| Type | Example | Description |
|------|---------|-------------|
| Basic scalars | `int`, `str`, `bool`, `float` | Simple values |
| Collections | `list[str]`, `dict[str, int]` | Lists and dictionaries |
| Optional | `str \| None`, `Optional[float]` | Nullable parameters |
| Union | `str \| int` | Multiple accepted types |
| Literal | `Literal["A", "B", "C"]` | Restricted values |
| Enum | `MyEnum` | Enumerated choices |
| Pydantic models | `UserData` | Complex structured data |

---

## 5. Async Handling

### Async with MongoDB (Motor)

```python
from motor.motor_asyncio import AsyncIOMotorClient
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mongodb-server")

client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["mydatabase"]

@mcp.tool()
async def find_documents(
    collection: str,
    query: dict = {},
    limit: int = 10
) -> list[dict]:
    """Find documents in a MongoDB collection."""
    cursor = db[collection].find(query).limit(limit)
    documents = await cursor.to_list(length=limit)
    # Convert ObjectId to string for JSON serialization
    for doc in documents:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
    return documents
```

### Context Object for Progress Reporting

```python
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("progress-server")

@mcp.tool()
async def long_running_task(
    items: list[str],
    ctx: Context
) -> str:
    """Process items with progress updates."""
    results = []

    await ctx.info("Starting processing...")

    for i, item in enumerate(items):
        await ctx.report_progress(
            progress=i,
            total=len(items),
            message=f"Processing item {i + 1}/{len(items)}"
        )
        results.append(f"Processed: {item}")

    await ctx.info("Processing complete!")
    return "\n".join(results)
```

### Context Logging Methods

```python
@mcp.tool()
async def tool_with_logging(data: str, ctx: Context) -> str:
    """Tool demonstrating all logging levels."""
    await ctx.debug("Debug message - detailed info")
    await ctx.info("Info message - general progress")
    await ctx.warning("Warning message - potential issues")
    await ctx.error("Error message - something went wrong")
    return "Done"
```

---

## 6. Claude Code Integration - Configuration

### Configuration File Locations

| Scope | Location | Purpose |
|-------|----------|---------|
| **local** | `.mcp.json` in project root | Project-specific, personal |
| **project** | `.mcp.json` in project root | Shared via version control |
| **user** | `~/.claude.json` | Global, all projects |

### JSON Configuration Format

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "mongodb-tools": {
      "type": "stdio",
      "command": "python",
      "args": ["/absolute/path/to/your/mcp_server.py"],
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "DATABASE_NAME": "mydb"
      }
    }
  }
}
```

### Environment Variable Expansion

```json
{
  "mcpServers": {
    "database": {
      "type": "stdio",
      "command": "python",
      "args": ["${HOME}/projects/mcp-server/server.py"],
      "env": {
        "DB_URI": "${MONGODB_URI:-mongodb://localhost:27017}",
        "API_KEY": "${API_KEY}"
      }
    }
  }
}
```

**Syntax:**
- `${VAR}` - Use environment variable value
- `${VAR:-default}` - Use default if variable not set

### CLI Commands for Managing Servers

```bash
# Add a stdio server
claude mcp add --transport stdio mongodb-tools -- python /path/to/server.py

# Add with environment variables
claude mcp add --transport stdio mongodb-tools \
  --env MONGODB_URI=mongodb://localhost:27017 \
  -- python /path/to/server.py

# List configured servers
claude mcp list

# Get server details
claude mcp get mongodb-tools

# Remove a server
claude mcp remove mongodb-tools

# Check server status (within Claude Code)
/mcp
```

---

## 7. Error Handling

### Using ToolError (Recommended)

```python
from mcp.server.fastmcp import FastMCP
from fastmcp.exceptions import ToolError

mcp = FastMCP("error-handling-server")

@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ToolError("Division by zero is not allowed")
    return a / b

@mcp.tool()
async def query_collection(collection: str) -> list[dict]:
    """Query a MongoDB collection."""
    allowed_collections = ["users", "products", "orders"]
    if collection not in allowed_collections:
        raise ToolError(f"Collection '{collection}' not accessible. Allowed: {allowed_collections}")
    # ... perform query
```

### Comprehensive Error Handling Pattern

```python
from mcp.server.fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
import logging

# Configure logging to stderr (IMPORTANT: never log to stdout)
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

mcp = FastMCP("mongodb-server", mask_error_details=True)

@mcp.tool()
async def find_documents(
    collection: str,
    query: dict = {},
    limit: int = 10,
    ctx: Context = None
) -> list[dict]:
    """Find documents with comprehensive error handling."""

    # Input validation
    if not collection:
        raise ToolError("Collection name is required")

    if limit < 1 or limit > 1000:
        raise ToolError("Limit must be between 1 and 1000")

    try:
        if ctx:
            await ctx.info(f"Querying collection: {collection}")

        cursor = db[collection].find(query).limit(limit)
        documents = await cursor.to_list(length=limit)

        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

        return documents

    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise ToolError("Database connection failed. Please try again later.")

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise ToolError("An unexpected error occurred")
```

---

## Sources

- [GitHub - modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- [MCP PyPI Package](https://pypi.org/project/mcp/)
- [Build an MCP Server - Official Docs](https://modelcontextprotocol.io/docs/develop/build-server)
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp)
- [FastMCP Tools Documentation](https://gofastmcp.com/servers/tools)
- [FastMCP Context Documentation](https://gofastmcp.com/servers/context)
