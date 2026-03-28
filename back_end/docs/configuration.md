# Configuration Guide

## Overview

The NLM Backend uses a two-tier configuration system designed to:

1. Keep sensitive credentials out of the repository
2. Allow environment-specific configurations
3. Support both local development and MongoDB Atlas deployments

## Configuration Files

### File Hierarchy

```
back_end/
|-- db_connector/
|   |-- mongo_credentials_path.env       # Tier 1: Points to credentials
|
# External (not in repo):
/secure/location/
|-- nlm_credentials.env                  # Tier 2: Actual credentials
```

---

## Server Configuration

`FAST_API_PORT` is the only server-level configuration variable. It is read directly from the OS environment by `main.py` with no `.env` file loading:

```python
# main.py
FAST_API_PORT = int(os.getenv('FAST_API_PORT', 8221))
```

Set it in your shell before starting the server if you need a non-default port:

```bash
FAST_API_PORT=9000 python main.py
```

---

## Two-Tier Credential System

### Purpose

The two-tier system prevents accidental credential exposure by:

1. Storing only a *path* to credentials in the repository
2. Keeping actual secrets in an external file

### Tier 1: mongo_credentials_path.env

Located at: `back_end/db_connector/mongo_credentials_path.env`

This file is tracked in the repository and contains:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_CREDENTIALS_PATH` | Yes | Absolute path to Tier 2 file |
| `DATABASE_NAME` | Yes | Target MongoDB database name |

**Example**:
```env
# mongo_credentials_path.env
MONGODB_CREDENTIALS_PATH="/home/user/secure/mongodb_atlas.env"
DATABASE_NAME="nlm_db"   # Required — server raises ValueError if absent
```

### Tier 2: Actual Credentials File

Located at: Path specified in `MONGODB_CREDENTIALS_PATH`

This file should NOT be in the repository and contains:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_CONNECTION_STRING` | Yes | Full MongoDB connection URI |

**Example**:
```env
# mongodb_atlas.env (external file)
MONGODB_CONNECTION_STRING="mongodb+srv://username:password@cluster0.abc123.mongodb.net/"
```

### Loading Process

```python
# db_connector/settings.py - MongoDBSettings.create_from_credentials()

# Step 1: Read Tier 1 file
credentials_path_file = Path(__file__).parent / "mongo_credentials_path.env"
# Extract MONGODB_CREDENTIALS_PATH and DATABASE_NAME

# Step 2: Read Tier 2 file
actual_credentials_file = Path(credentials_path)
# Extract MONGODB_CONNECTION_STRING
# Set environment variables

# Step 3: Create settings instance
return cls(
    mongodb_connection_string=connection_string,
    database_name=database_name
)
```

---

## MongoDB Connection Settings

### Connection Pool Configuration

Defined in `db_connector/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `min_pool_size` | 1 | Minimum connections in pool |
| `max_pool_size` | 10 | Maximum connections in pool |
| `max_idle_time_ms` | 30000 | Max idle time before connection is closed |
| `server_selection_timeout_ms` | 5000 | Time to wait for server selection |
| `connect_timeout_ms` | 10000 | Connection establishment timeout |
| `socket_timeout_ms` | 30000 | Socket operation timeout |

### Connection Options

These are passed to the Motor AsyncIOMotorClient:

```python
def get_connection_options(self) -> dict:
    return {
        "minPoolSize": self.min_pool_size,
        "maxPoolSize": self.max_pool_size,
        "maxIdleTimeMS": self.max_idle_time_ms,
        "serverSelectionTimeoutMS": self.server_selection_timeout_ms,
        "connectTimeoutMS": self.connect_timeout_ms,
        "socketTimeoutMS": self.socket_timeout_ms,
        "retryWrites": True,
        "retryReads": True,
    }
```

### MongoDB URI Format

**MongoDB Atlas (SRV)**:
```
mongodb+srv://username:password@cluster0.abc123.mongodb.net/
```

**Local MongoDB**:
```
mongodb://localhost:27017/
```

**With Authentication**:
```
mongodb://username:password@localhost:27017/?authSource=admin
```

---

## Chat Configuration (`~/.nlm/chat_config.json`)

The chat/translation system stores LLM provider settings in a JSON file outside the codebase. This file is auto-created with defaults on first chat attempt.

**Location**: `~/.nlm/chat_config.json` (permissions: `0o600`)

| Key | Default | Description |
|-----|---------|-------------|
| `llm_provider` | `"anthropic"` | `"anthropic"` or `"local"` |
| `anthropic_api_key` | `""` | Anthropic API key (required for Anthropic provider) |
| `anthropic_model` | `"claude-sonnet-4-6"` | Claude model to use |
| `local_base_url` | `"http://127.0.0.1:8080"` | Local LLM server URL |
| `local_model` | `"default"` | Model name for local server |
| `local_context_window` | `128000` | Context window size for local LLM |
| `dev_features` | `{}` | Developer feature flags |

**Important**: If `anthropic_api_key` is blank when using the Anthropic provider, the chat stream returns an SSE error event: "Anthropic API key not configured. Set it in Chat Settings."

You can configure this via the app UI (**Settings > Chat Config**) or by editing the file directly.

See [chat-system.md](./chat-system.md) for full details on the AI/chat architecture.

---

## Environment Setup Guide

### Local Development Setup

MongoDB is bundled with the Electron frontend. When running the backend standalone, start the bundled `mongod` manually first (see README.md for the full command).

#### 1. Create Credentials File

```bash
mkdir -p ~/.nlm
echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27019"' > ~/.nlm/mongodb_credentials.env
chmod 600 ~/.nlm/mongodb_credentials.env
```

#### 2. Configure Tier 1 (mongo_credentials_path.env)

```env
# back_end/db_connector/mongo_credentials_path.env
MONGODB_CREDENTIALS_PATH='/home/YOUR_USER/.nlm/mongodb_credentials.env'
DATABASE_NAME='nlm_db'
```

#### 3. Verify Connection

```bash
mongosh --port 27019 --eval "db.runCommand({ping: 1})"
# Expected: { ok: 1 }
```

---

### Atlas Deployment Setup

For production or cloud development, use MongoDB Atlas:

1. **Create Tier 2 credentials file**:
   ```bash
   mkdir -p ~/secure
   touch ~/secure/nlm_credentials.env
   chmod 600 ~/secure/nlm_credentials.env
   ```

2. **Add Atlas credentials**:
   ```env
   # ~/secure/nlm_credentials.env
   MONGODB_CONNECTION_STRING="mongodb+srv://user:pass@cluster.mongodb.net/"
   ```

3. **Configure Tier 1**:
   ```env
   # back_end/db_connector/mongo_credentials_path.env
   MONGODB_CREDENTIALS_PATH="/home/youruser/secure/nlm_credentials.env"
   DATABASE_NAME="nlm_db"
   ```

### Production Considerations

1. **Use environment variables** instead of files where possible
2. **Restrict file permissions**: `chmod 600` on credential files
3. **Use secrets management** (Vault, AWS Secrets Manager, etc.)
4. **Rotate API keys** regularly
5. **Use different credentials** for dev/staging/prod

---

## Logging Configuration

Located at: `back_end/pytest.ini` (for tests)

```ini
[pytest]
log_cli = true
log_level = DEBUG
log_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s
log_date_format = %Y-%m-%d %H:%M:%S
```

### Runtime Logging

In `main.py`:
```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

---

## Troubleshooting

### Common Issues

**1. "Credentials path file not found"**
- Ensure `mongo_credentials_path.env` exists in `db_connector/`
- Check file contains `MONGODB_CREDENTIALS_PATH=...`

**2. "MongoDB credentials file not found"**
- Verify the path in `MONGODB_CREDENTIALS_PATH` is correct
- Check file permissions allow reading

**3. "MongoDB URI must start with mongodb:// or mongodb+srv://"**
- Ensure connection string uses one of these prefixes
- Atlas connections use `mongodb+srv://`; local connections use `mongodb://`

**4. Connection timeouts**
- Check network connectivity to MongoDB Atlas
- Verify IP whitelist in Atlas dashboard
- Increase `server_selection_timeout_ms` if needed

### Validation Script

Test your configuration:

```bash
cd back_end
python -c "
from db_connector.settings import MongoDBSettings
settings = MongoDBSettings.create_from_credentials()
print(f'Database: {settings.database_name}')
print(f'Connection configured: {bool(settings.mongodb_connection_string)}')
print(settings)
"
```

### Connection Test

```bash
cd back_end
pytest tests/unit/db_connector/test_mongodb_connection.py -v
```