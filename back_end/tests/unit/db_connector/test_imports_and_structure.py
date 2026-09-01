"""
Test suite for db_connector module structure.
Asserts the public contract (method names, property type) of MongoDBSettings
and MongoDBConnector. Pure tautological imports/file-existence checks were
removed — failed imports fire ImportError before any assertion would run.
"""

import pytest


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
