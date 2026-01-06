"""
Tests for schema_definition.py - the single source of truth for MongoDB schema.

TDD Step 1: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/schema_enforcer/test_schema_definition.py -v
"""

import pytest


class TestExpectedCollections:
    """Tests for EXPECTED_COLLECTIONS schema definition"""

    def test_expected_collections_has_six_entries(self):
        """Schema defines exactly 6 collections"""
        from utils.schema_enforcer.schema_definition import EXPECTED_COLLECTIONS

        assert len(EXPECTED_COLLECTIONS) == 6
        assert set(EXPECTED_COLLECTIONS.keys()) == {
            "languages",
            "bible_books",
            "bible_texts",
            "base_structure_bible",
            "dictionaries",
            "grammar_systems",
        }

    def test_all_collections_have_required_fields(self):
        """Every collection defines required_fields dict"""
        from utils.schema_enforcer.schema_definition import EXPECTED_COLLECTIONS

        for name, schema in EXPECTED_COLLECTIONS.items():
            assert "required_fields" in schema, f"{name} missing required_fields"
            assert isinstance(
                schema["required_fields"], dict
            ), f"{name} required_fields should be dict"

    def test_all_collections_have_indexes(self):
        """Every collection defines at least one index"""
        from utils.schema_enforcer.schema_definition import EXPECTED_COLLECTIONS

        for name, schema in EXPECTED_COLLECTIONS.items():
            assert "indexes" in schema, f"{name} missing indexes"
            assert len(schema["indexes"]) >= 1, f"{name} needs at least one index"

    def test_index_specs_have_keys(self):
        """Every index spec has a 'keys' field with proper structure"""
        from utils.schema_enforcer.schema_definition import EXPECTED_COLLECTIONS

        for name, schema in EXPECTED_COLLECTIONS.items():
            for idx in schema["indexes"]:
                assert "keys" in idx, f"{name} index missing keys"
                assert isinstance(idx["keys"], list), f"{name} index keys should be list"
                # Each key should be a tuple of (field_name, direction)
                for key in idx["keys"]:
                    assert isinstance(key, tuple), f"{name} index key should be tuple"
                    assert len(key) == 2, f"{name} index key should be (field, direction)"


class TestDeprecatedCollections:
    """Tests for DEPRECATED_COLLECTIONS definition"""

    def test_deprecated_collections_is_list(self):
        """DEPRECATED_COLLECTIONS is defined as a list"""
        from utils.schema_enforcer.schema_definition import DEPRECATED_COLLECTIONS

        assert isinstance(DEPRECATED_COLLECTIONS, list)
        # bible_books was moved to EXPECTED_COLLECTIONS - it IS actively used


class TestSchemaVersion:
    """Tests for schema versioning"""

    def test_schema_version_defined(self):
        """SCHEMA_VERSION is defined and follows semver format"""
        from utils.schema_enforcer.schema_definition import SCHEMA_VERSION

        assert SCHEMA_VERSION is not None
        # Should be semver format: X.Y.Z
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 3, "SCHEMA_VERSION should be X.Y.Z format"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"
