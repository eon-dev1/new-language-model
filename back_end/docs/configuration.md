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
|-- fastapi.env                          # Server configuration
|-- db_connector/
|   |-- mongo_credentials_path.env       # Tier 1: Points to credentials
|
# External (not in repo):
/secure/location/
|-- nlm_credentials.env                  # Tier 2: Actual credentials
```

---

## Server Configuration (fastapi.env)

Located at: `back_end/fastapi.env`

### Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CREDENTIALS_PATH` | No | - | Path to credentials file (optional, for MongoDB credentials) |
| `FAST_API_PORT` | No | 8221 | Port for the FastAPI server |

**Note**: `CREDENTIALS_PATH` is optional for local development. API authentication has been disabled - MongoDB provides its own authentication layer.

### Example

```env
# fastapi.env
CREDENTIALS_PATH="/home/user/secure/nlm_credentials.env"
FAST_API_PORT=8221
```

### How It's Loaded

```python
# main.py
env_path = os.path.join(os.path.dirname(__file__), 'fastapi.env')
load_dotenv(env_path)

CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', '').strip('"')
if CREDENTIALS_PATH and os.path.exists(CREDENTIALS_PATH):
    load_dotenv(CREDENTIALS_PATH, override=True)

FAST_API_KEY = os.getenv('FAST_API_KEY')
FAST_API_PORT = int(os.getenv('FAST_API_PORT', 8221))
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
DATABASE_NAME="nlm_db"
```

### Tier 2: Actual Credentials File

Located at: Path specified in `MONGODB_CREDENTIALS_PATH`

This file should NOT be in the repository and contains:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_CONNECTION_STRING` | Yes | Full MongoDB connection URI |
| `FAST_API_KEY` | No | Deprecated - API authentication disabled for local development |

**Note**: `FAST_API_KEY` is no longer required. API authentication has been disabled because:
- MongoDB provides its own authentication layer
- The server binds to localhost only (127.0.0.1)
- Simplifies local development workflow

**Example**:
```env
# mongodb_atlas.env (external file)
MONGODB_CONNECTION_STRING="mongodb+srv://username:password@cluster0.abc123.mongodb.net/"
# FAST_API_KEY not required - authentication disabled for local development
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

## Atlas-Specific Configuration

Located at: `back_end/config/atlas.py`

For MongoDB Atlas deployments with additional features:

### AtlasSettings

| Setting | Default | Description |
|---------|---------|-------------|
| `atlas_connection_string` | Required | mongodb+srv:// connection string |
| `database_name` | nlm_database | Target database |
| `atlas_app_name` | nlm-fastapi | Application name for Atlas monitoring |
| `max_pool_size` | 100 | Maximum connection pool size |
| `min_pool_size` | 10 | Minimum connection pool size |
| `server_selection_timeout_ms` | 5000 | Server selection timeout |
| `retry_writes` | true | Enable write retry |
| `write_concern_w` | majority | Write concern level |
| `read_preference` | primary | Read preference |

### Validation Rules

```python
@validator("atlas_connection_string")
def validate_atlas_connection_string(cls, v):
    if not v.startswith("mongodb+srv://"):
        raise ValueError("Atlas connection string must use mongodb+srv:// protocol")
    if "mongodb.net" not in v:
        raise ValueError("Atlas connection string must contain 'mongodb.net' domain")
    return v
```

---

## Alternative MongoDB Configuration

Located at: `back_end/config/mongodb.py`

Supports both local and Atlas deployments with individual parameters:

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | - | Full connection string (overrides individual settings) |
| `MONGODB_HOST` | localhost | MongoDB host |
| `MONGODB_PORT` | 27017 | MongoDB port |
| `MONGODB_USERNAME` | - | Authentication username |
| `MONGODB_PASSWORD` | - | Authentication password |
| `MONGODB_DATABASE` | nlm_db | Database name |
| `MONGODB_AUTH_SOURCE` | admin | Authentication database |
| `MONGODB_USE_TLS` | auto | Enable TLS (auto-detected for Atlas) |
| `MONGODB_MAX_POOL_SIZE` | 100 | Max pool size |
| `MONGODB_MIN_POOL_SIZE` | 0 | Min pool size |

### Auto-Detection

TLS is automatically enabled when:
- Connection string contains `mongodb+srv://`
- Connection string contains `mongodb.net`
- Host contains `atlas` or `mongodb.net`

---

## Application Settings

Combined settings class in `config/atlas.py`:

```python
class ApplicationSettings(BaseSettings):
    app_name: str = "NLM FastAPI Endpoint"
    debug: bool = False
    log_level: str = "INFO"       # DEBUG, INFO, WARNING, ERROR, CRITICAL
    api_key: Optional[str] = None
    api_port: int = 8221

    # Nested settings
    atlas: AtlasSettings
    mem0: Mem0Settings  # For vector embeddings (optional)
```

---

## Environment Setup Guide

### Local Development with Docker MongoDB (Recommended)

For development, use a local MongoDB instance via Docker to avoid external dependencies.

#### 1. Start MongoDB Container

```bash
# Using docker-compose (recommended)
cd back_end/docker && docker compose up -d

# Or manually run MongoDB on port 27018
docker run -d \
  --name nlm-mongodb \
  -p 27018:27017 \
  -v nlm-mongo-data:/data/db \
  mongo:8.0
```

| Flag | Purpose |
|------|---------|
| `-d` | Run in background (detached) |
| `--name nlm-mongodb` | Container name for easy reference |
| `-p 27018:27017` | Map host port 27018 → container port 27017 |
| `-v nlm-mongo-data:/data/db` | Persist data in named volume |

#### 2. Create Credentials File

```bash
mkdir -p ~/.nlm
echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27018"' > ~/.nlm/mongodb_credentials.env
chmod 600 ~/.nlm/mongodb_credentials.env
```

#### 3. Configure Tier 1 (mongo_credentials_path.env)

```env
# back_end/db_connector/mongo_credentials_path.env
MONGODB_CREDENTIALS_PATH='/home/YOUR_USER/.nlm/mongodb_credentials.env'
DATABASE_NAME='nlm_db'
```

#### 4. Configure Server (fastapi.env)

```env
# back_end/fastapi.env
CREDENTIALS_PATH="/home/YOUR_USER/.nlm/mongodb_credentials.env"
FAST_API_PORT=8221
```

#### 5. Verify Connection

```bash
mongosh --port 27018 --eval "db.runCommand({ping: 1})"
# Expected: { ok: 1 }
```

#### Docker Container Management

```bash
docker ps --filter name=nlm-mongodb  # Check status
docker stop nlm-mongodb              # Stop
docker start nlm-mongodb             # Restart
docker logs nlm-mongodb              # View logs
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
   # FAST_API_KEY not required - authentication disabled for local development
   ```

3. **Configure Tier 1**:
   ```env
   # back_end/db_connector/mongo_credentials_path.env
   MONGODB_CREDENTIALS_PATH="/home/youruser/secure/nlm_credentials.env"
   DATABASE_NAME="nlm_db"
   ```

4. **Configure server**:
   ```env
   # back_end/fastapi.env
   CREDENTIALS_PATH="/home/youruser/secure/nlm_credentials.env"
   FAST_API_PORT=8221
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

**1. "FAST_API_KEY not found"**
- This warning can be ignored - API authentication is disabled for local development
- The server will start without an API key

**2. "Credentials path file not found"**
- Ensure `mongo_credentials_path.env` exists in `db_connector/`
- Check file contains `MONGODB_CREDENTIALS_PATH=...`

**3. "MongoDB credentials file not found"**
- Verify the path in `MONGODB_CREDENTIALS_PATH` is correct
- Check file permissions allow reading

**4. "MongoDB URI must start with mongodb://"**
- Ensure connection string format is correct
- Atlas requires `mongodb+srv://` prefix

**5. Connection timeouts**
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