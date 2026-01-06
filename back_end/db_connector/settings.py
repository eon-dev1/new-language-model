# db_connector/core/settings.py
# MongoDB connection settings 

"""
Uses mongo_credentials_path.env which contains:
- MONGODB_CREDENTIALS_PATH="path/to/actual/credentials/file"
- DATABASE_NAME="database_name"

The actual credentials file should contain: MONGODB_CONNECTION_STRING="[connection string]"

"""

import os
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
        """Create settings instance with two-tier credential loading"""
        
        # Step 1: Load path to actual credentials and database name from mongo_credentials_path.env
        credentials_path_file = Path(__file__).parent / "mongo_credentials_path.env"
        
        if not credentials_path_file.exists():
            raise FileNotFoundError(f"Credentials path file not found: {credentials_path_file}")

        # Read the path to the actual credentials file and database name
        credentials_path = None
        database_name = None
        
        with open(credentials_path_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    if key == "MONGODB_CREDENTIALS_PATH":
                        credentials_path = value
                    elif key == "DATABASE_NAME":
                        database_name = value
        
        if not credentials_path:
            raise ValueError("MONGODB_CREDENTIALS_PATH not found in mongo_credentials_path.env")
        
        if not database_name:
            raise ValueError("DATABASE_NAME not found in mongo_credentials_path.env")
        
        # Step 2: Load actual MongoDB credentials from the specified file
        actual_credentials_file = Path(credentials_path)
        if not actual_credentials_file.exists():
            raise FileNotFoundError(f"MongoDB credentials file not found: {actual_credentials_file}")
        
        # Load environment variables from actual credentials file
        with open(actual_credentials_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        
        logger.info(f"Loaded MongoDB credentials from {actual_credentials_file}")
        
        # Verify connection string was loaded
        connection_string = os.environ.get("MONGODB_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("MONGODB_CONNECTION_STRING not found in credentials file")
        
        # Create and return settings instance with loaded database name
        return cls(
            mongodb_connection_string=connection_string,
            database_name=database_name
        )
    
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