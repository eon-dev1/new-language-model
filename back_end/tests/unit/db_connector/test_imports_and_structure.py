"""
Test suite for db_connector module structure and imports.
Tests all imports, module structure, and basic functionality.

Migrated from db_connector/__tests_db_connector__/
"""

import importlib
from pathlib import Path

import pytest


# Path to db_connector module (relative to back_end/)
DB_CONNECTOR_PATH = Path(__file__).parent.parent.parent.parent / "db_connector"


class TestDbConnectorStructure:
    """Test db_connector module structure and file organization."""

    def test_db_connector_directory_exists(self):
        """Test that db_connector directory exists."""
        assert DB_CONNECTOR_PATH.exists()
        assert DB_CONNECTOR_PATH.is_dir()

    @pytest.mark.parametrize("file_name", [
        "__init__.py",
        "settings.py",
        "connection.py",
        "mongo_credentials_path.env"
    ])
    def test_required_files_exist(self, file_name):
        """Test that all required files exist."""
        file_path = DB_CONNECTOR_PATH / file_name
        assert file_path.exists(), f"Required file {file_name} does not exist at {file_path}"


class TestDbConnectorImports:
    """Test all imports in db_connector module work correctly."""

    def test_can_import_db_connector_package(self):
        """Test that db_connector can be imported as a package."""
        import db_connector
        assert db_connector is not None

    def test_can_import_settings_module(self):
        """Test that settings module can be imported."""
        from db_connector import settings
        assert settings is not None

    def test_can_import_connection_module(self):
        """Test that connection module can be imported."""
        from db_connector import connection
        assert connection is not None

    def test_can_import_mongodb_settings_class(self):
        """Test that MongoDBSettings class can be imported."""
        from db_connector.settings import MongoDBSettings
        assert callable(MongoDBSettings)

    def test_can_import_mongodb_connector_class(self):
        """Test that MongoDBConnector class can be imported."""
        from db_connector.connection import MongoDBConnector
        assert callable(MongoDBConnector)


class TestRequiredDependencies:
    """Test that all required dependencies are available."""

    def test_motor_available(self):
        """Test that Motor (MongoDB async driver) is available."""
        import motor
        import motor.motor_asyncio
        assert motor is not None
        assert motor.motor_asyncio is not None

    def test_pymongo_available(self):
        """Test that PyMongo is available."""
        import pymongo
        assert pymongo is not None

    def test_pydantic_available(self):
        """Test that Pydantic is available."""
        import pydantic
        assert pydantic is not None

    def test_pydantic_settings_available(self):
        """Test that pydantic-settings is available."""
        import pydantic_settings
        from pydantic_settings import BaseSettings
        assert pydantic_settings is not None
        assert BaseSettings is not None

    def test_dnspython_available(self):
        """Test that dnspython (required for MongoDB SRV records) is available."""
        import dns
        import dns.resolver
        assert dns is not None


class TestClassStructure:
    """Test that classes have the expected structure and methods."""

    def test_mongodb_settings_class_structure(self):
        """Test MongoDBSettings class has required methods and attributes."""
        from db_connector.settings import MongoDBSettings

        assert hasattr(MongoDBSettings, 'create_from_credentials')
        assert callable(getattr(MongoDBSettings, 'create_from_credentials'))
        assert hasattr(MongoDBSettings, 'get_connection_options')

    @pytest.mark.parametrize("method_name", ['connect', 'disconnect', 'get_database'])
    def test_mongodb_connector_methods(self, method_name):
        """Test MongoDBConnector class has required methods."""
        from db_connector.connection import MongoDBConnector

        assert hasattr(MongoDBConnector, method_name), \
            f"MongoDBConnector missing required method: {method_name}"
        method = getattr(MongoDBConnector, method_name)
        assert callable(method), f"MongoDBConnector.{method_name} is not callable"

    @pytest.mark.parametrize("property_name", ['is_connected'])
    def test_mongodb_connector_properties(self, property_name):
        """Test MongoDBConnector class has required properties."""
        from db_connector.connection import MongoDBConnector

        assert hasattr(MongoDBConnector, property_name), \
            f"MongoDBConnector missing required property: {property_name}"
        attr = getattr(MongoDBConnector, property_name)
        assert isinstance(attr, property), \
            f"MongoDBConnector.{property_name} should be a property"


class TestEnvironmentConfiguration:
    """Test environment configuration and credential loading."""

    def test_credentials_path_file_exists(self):
        """Test that mongo_credentials_path.env file exists."""
        credentials_path_file = DB_CONNECTOR_PATH / "mongo_credentials_path.env"
        assert credentials_path_file.exists()

    def test_credentials_path_file_readable(self):
        """Test that mongo_credentials_path.env file is readable."""
        credentials_path_file = DB_CONNECTOR_PATH / "mongo_credentials_path.env"
        with open(credentials_path_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert isinstance(content, str)
            assert len(content.strip()) > 0

    @pytest.mark.parametrize("required_key", ['MONGODB_CREDENTIALS_PATH', 'DATABASE_NAME'])
    def test_credentials_path_file_contains_required_keys(self, required_key):
        """Test that mongo_credentials_path.env contains required configuration keys."""
        credentials_path_file = DB_CONNECTOR_PATH / "mongo_credentials_path.env"

        found_keys = set()

        with open(credentials_path_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key = line.split('=', 1)[0].strip()
                    found_keys.add(key)

        assert required_key in found_keys, \
            f"Required key '{required_key}' not found in mongo_credentials_path.env"


class TestModuleInitialization:
    """Test that modules can be initialized without errors."""

    def test_settings_module_loads_without_error(self):
        """Test that settings module can be loaded without import errors."""
        importlib.reload(importlib.import_module('db_connector.settings'))

    def test_connection_module_loads_without_error(self):
        """Test that connection module can be loaded without import errors."""
        importlib.reload(importlib.import_module('db_connector.connection'))
