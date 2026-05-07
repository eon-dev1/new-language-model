# db_connector/settings.py
# MongoDB connection settings

"""
Credentials are loaded from ~/.nlm/mongodb_credentials.env — single file, outside the repo.

The file must contain:
    MONGODB_CONNECTION_STRING="<uri>"   (required)
    DATABASE_NAME="<name>"              (optional; defaults to "nlm_translator")
"""

from pathlib import Path
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)

class MongoDBSettings(BaseSettings):
    """MongoDB Atlas connection settings"""

    # MongoDB connection parameters
    mongodb_connection_string: str = Field(..., description="Complete MongoDB Atlas connection URI")
    database_name: str = Field(default="nlm_translator", description="Target database name")

    # Connection pool settings
    min_pool_size: int = Field(default=1, description="Minimum connection pool size")
    max_pool_size: int = Field(default=10, description="Maximum connection pool size")
    max_idle_time_ms: int = Field(default=30000, description="Max idle time for connections")

    # Server selection and timeout settings
    server_selection_timeout_ms: int = Field(default=5000, description="Server selection timeout")
    connect_timeout_ms: int = Field(default=10000, description="Connection timeout")
    socket_timeout_ms: int = Field(default=30000, description="Socket timeout")
    
    # Health check settings
    health_check_interval: int = Field(default=30, description="Health check interval in seconds")
    max_reconnect_attempts: int = Field(default=5, description="Maximum reconnection attempts")

    model_config = ConfigDict(case_sensitive=False)

    @field_validator("mongodb_connection_string")
    @classmethod
    def validate_mongodb_uri(cls, v: str) -> str:
        """Validate MongoDB URI format"""
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MongoDB URI must start with mongodb:// or mongodb+srv://")
        return v

    @field_validator("database_name")
    @classmethod
    def validate_database_name(cls, v: str) -> str:
        """Validate database name format"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Database name cannot be empty")
        return v.strip()
    
    @classmethod
    def create_from_credentials(cls) -> "MongoDBSettings":
        """Load MongoDB settings from ~/.nlm/mongodb_credentials.env.

        The file must contain MONGODB_CONNECTION_STRING. DATABASE_NAME is
        optional; if absent, the class default ("nlm_translator") applies.
        """
        creds_file = Path.home() / ".nlm" / "mongodb_credentials.env"
        if not creds_file.is_file():
            raise FileNotFoundError(
                f"MongoDB credentials file not found: {creds_file}\n"
                f"Create it with MONGODB_CONNECTION_STRING=\"<uri>\"."
            )

        def _unquote(s: str) -> str:
            # Strip a matched quote pair only (avoids mangling mixed-quote values).
            if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
                return s[1:-1]
            return s

        values: dict[str, str] = {}
        for line in creds_file.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            values[key.strip()] = _unquote(raw.strip())

        if "MONGODB_CONNECTION_STRING" not in values:
            raise ValueError(
                f"MONGODB_CONNECTION_STRING missing from {creds_file}"
            )

        kwargs = {"mongodb_connection_string": values["MONGODB_CONNECTION_STRING"]}
        if "DATABASE_NAME" in values:
            kwargs["database_name"] = values["DATABASE_NAME"]

        return cls(**kwargs)
    
    def get_connection_options(self) -> dict:
        """Get Motor client connection options"""
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
    
    @property
    def mongodb_uri(self) -> str:
        """Alias for backward compatibility"""
        return self.mongodb_connection_string
    
    def __str__(self) -> str:
        """String representation hiding sensitive information"""
        return f"MongoDBSettings(database={self.database_name}, pool_size={self.min_pool_size}-{self.max_pool_size})"