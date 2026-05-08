# Configuration Guide

## Overview

The NLM Backend keeps all secrets out of the repository by reading credentials from a single file outside the repo:

```
~/.nlm/mongodb_credentials.env    # MongoDB credentials (never in repo)
~/.nlm/chat_config.json           # LLM provider settings (auto-created on first use)
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

## MongoDB Credentials

### Credentials File

Located at: `~/.nlm/mongodb_credentials.env` (never tracked in the repo)

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_CONNECTION_STRING` | Yes | Full MongoDB connection URI |
| `DATABASE_NAME` | No | Target database name (default: `"nlm_translator"`) |

**Example**:
```env
# ~/.nlm/mongodb_credentials.env
MONGODB_CONNECTION_STRING="mongodb+srv://username:password@cluster0.abc123.mongodb.net/"
DATABASE_NAME="nlm_translator"
```

### Loading Process

`MongoDBSettings.create_from_credentials()` in `db_connector/settings.py`:

1. Opens `~/.nlm/mongodb_credentials.env` — raises `FileNotFoundError` if absent
2. Parses `KEY=VALUE` lines, stripping matched quote pairs
3. Raises `ValueError` if `MONGODB_CONNECTION_STRING` is missing
4. `DATABASE_NAME` is optional; if absent, the class default `"nlm_translator"` applies

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
| `health_check_interval` | 30 | Seconds between health checks |
| `max_reconnect_attempts` | 5 | Maximum reconnection attempts |

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
| `llm_provider` | `"anthropic"` | `"anthropic"`, `"openrouter"`, or `"local"` |
| `anthropic_api_key` | `""` | Anthropic API key (required for `anthropic` provider) |
| `anthropic_model` | `"claude-sonnet-4-6"` | Claude model to use |
| `openrouter_api_key` | `""` | OpenRouter API key (required for `openrouter` provider) |
| `openrouter_model` | `"anthropic/claude-sonnet-4.6"` | Model ID passed to OpenRouter |
| `local_base_url` | `"http://127.0.0.1:8080"` | Local LLM server URL |
| `local_model` | `"default"` | Model name for local server |
| `local_context_window` | `128000` | Context window size for local LLM |
| `thinking_enabled` | `true` | Enable extended thinking for supported models |
| `dev_features` | `{}` | Developer feature flags (see below) |

**`dev_features` flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `book_of_enoch` | `false` | Enables 1 Enoch as book 67 in the canon. Intended for the rare scenario where a developer knows a low-resource language but it already has both Old and New Testament translations, which could be in the model's training data already. The book of Enoch has a chapter/verse structure and is less likely to be translated into any low resource language |

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

`DATABASE_NAME` is optional — omit it to use the default `nlm_translator`, or add a second line:
```env
DATABASE_NAME="nlm_translator"
```

#### 2. Verify Connection

```bash
mongosh --port 27019 --eval "db.runCommand({ping: 1})"
# Expected: { ok: 1 }
```

---

### Atlas Deployment Setup

For production or cloud development, use MongoDB Atlas:

1. **Create credentials file**:
   ```bash
   mkdir -p ~/.nlm
   chmod 700 ~/.nlm
   ```

2. **Add Atlas credentials**:
   ```env
   # ~/.nlm/mongodb_credentials.env
   MONGODB_CONNECTION_STRING="mongodb+srv://user:pass@cluster.mongodb.net/"
   DATABASE_NAME="nlm_translator"
   ```

3. **Restrict permissions**:
   ```bash
   chmod 600 ~/.nlm/mongodb_credentials.env
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

**1. "MongoDB credentials file not found"**
- Ensure `~/.nlm/mongodb_credentials.env` exists
- Check file permissions allow reading (`chmod 600 ~/.nlm/mongodb_credentials.env`)

**2. "MongoDB URI must start with mongodb:// or mongodb+srv://"**
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