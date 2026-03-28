"""
Tests for enforcer.py - SchemaEnforcer async class.

TDD Step 4: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/schema_enforcer/test_enforcer.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.unit.schema_enforcer.conftest import AsyncIterator


class TestCheckCollections:
    """Tests for collection presence checking"""

    @pytest.mark.asyncio
    async def test_check_collections_all_present(self, mock_db):
        """No missing collections when all exist"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Default mock_db already has all 6 collections
        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()
        assert report.missing_collections == []

    @pytest.mark.asyncio
    async def test_check_collections_one_missing(self, mock_db):
        """Reports missing collection"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Override to exclude grammar_systems
        mock_db.get_database().list_collection_names = AsyncMock(
            return_value=[
                "languages",
                "bible_books",
                "bible_texts",
                "base_structure_bible",
                "dictionaries",
                # grammar_systems missing
            ]
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()
        assert "grammar_systems" in report.missing_collections


class TestCheckIndexes:
    """Tests for index presence checking"""

    @pytest.mark.asyncio
    async def test_check_indexes_all_present(self, mock_db):
        """No missing indexes when all exist"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Set up bible_texts with all required indexes
        mock_db._collection_cache["bible_texts"] = AsyncMock()
        mock_db._collection_cache["bible_texts"].index_information = AsyncMock(
            return_value={
                "_id_": {"key": [("_id", 1)]},
                "verse_lookup": {
                    "key": [
                        ("language_code", 1),
                        ("book_code", 1),
                        ("chapter", 1),
                        ("verse", 1),
                        ("translation_type", 1),
                    ]
                },
                "language_type_filter": {
                    "key": [("language_code", 1), ("translation_type", 1)]
                },
                "book_type_filter": {
                    "key": [("book_code", 1), ("translation_type", 1)]
                },
            }
        )
        mock_db._collection_cache["bible_texts"].aggregate = MagicMock(
            return_value=AsyncIterator([])
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()

        # No bible_texts indexes should be missing
        bible_texts_missing = [
            idx for idx in report.missing_indexes if "bible_texts" in idx
        ]
        assert bible_texts_missing == []

    @pytest.mark.asyncio
    async def test_check_indexes_missing(self, mock_db):
        """Reports missing indexes"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # bible_texts only has _id index (all custom indexes missing)
        mock_db._collection_cache["bible_texts"] = AsyncMock()
        mock_db._collection_cache["bible_texts"].index_information = AsyncMock(
            return_value={"_id_": {"key": [("_id", 1)]}}
        )
        mock_db._collection_cache["bible_texts"].aggregate = MagicMock(
            return_value=AsyncIterator([])
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()

        assert "bible_texts.verse_lookup" in report.missing_indexes


class TestDryRunBehavior:
    """Tests for dry_run mode (check but don't modify)"""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_create(self, mock_db):
        """Dry run reports but doesn't call create_index"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Set up missing index
        mock_db._collection_cache["bible_texts"] = AsyncMock()
        mock_db._collection_cache["bible_texts"].index_information = AsyncMock(
            return_value={"_id_": {"key": [("_id", 1)]}}
        )
        mock_db._collection_cache["bible_texts"].aggregate = MagicMock(
            return_value=AsyncIterator([])
        )
        mock_db._collection_cache["bible_texts"].create_index = AsyncMock()

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        await enforcer.enforce()

        # create_index should not be called in dry_run mode
        mock_db._collection_cache["bible_texts"].create_index.assert_not_called()

    @pytest.mark.asyncio
    async def test_enforce_creates_missing_index(self, mock_db):
        """Enforce mode calls create_index for missing indexes"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Set up missing index
        mock_db._collection_cache["bible_texts"] = AsyncMock()
        mock_db._collection_cache["bible_texts"].index_information = AsyncMock(
            return_value={"_id_": {"key": [("_id", 1)]}}
        )
        mock_db._collection_cache["bible_texts"].aggregate = MagicMock(
            return_value=AsyncIterator([])
        )
        mock_db._collection_cache["bible_texts"].create_index = AsyncMock(
            return_value="verse_lookup"
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=False)
        await enforcer.enforce()

        # create_index should be called
        assert mock_db._collection_cache["bible_texts"].create_index.called


class TestDeprecatedCollections:
    """Tests for deprecated collection warnings"""

    @pytest.mark.asyncio
    async def test_deprecated_collection_warning(self, mock_db):
        """Warns when deprecated collection exists"""
        from unittest.mock import patch
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Patch DEPRECATED_COLLECTIONS to include a test collection
        with patch(
            "utils.schema_enforcer.enforcer.DEPRECATED_COLLECTIONS",
            ["old_legacy_collection"],
        ):
            # Include deprecated collection in list
            mock_db.get_database().list_collection_names = AsyncMock(
                return_value=[
                    "languages",
                    "bible_books",
                    "bible_texts",
                    "base_structure_bible",
                    "dictionaries",
                    "grammar_systems",
                    "old_legacy_collection",  # deprecated (via patch)
                ]
            )

            # Set up old_legacy_collection mock
            mock_db._collection_cache["old_legacy_collection"] = AsyncMock()
            mock_db._collection_cache["old_legacy_collection"].count_documents = (
                AsyncMock(return_value=0)
            )
            mock_db._collection_cache["old_legacy_collection"].index_information = (
                AsyncMock(return_value={"_id_": {"key": [("_id", 1)]}})
            )
            mock_db._collection_cache["old_legacy_collection"].aggregate = MagicMock(
                return_value=AsyncIterator([])
            )

            enforcer = SchemaEnforcer(mock_db, dry_run=True)
            report = await enforcer.enforce()

            assert any("old_legacy_collection" in w for w in report.warnings)


class TestUnexpectedCollections:
    """Tests for unexpected collection warnings"""

    @pytest.mark.asyncio
    async def test_unexpected_collection_warning(self, mock_db):
        """Warns about collections not in schema"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Include unexpected collection
        mock_db.get_database().list_collection_names = AsyncMock(
            return_value=[
                "languages",
                "bible_books",
                "bible_texts",
                "base_structure_bible",
                "dictionaries",
                "grammar_systems",
                "random_test_data",  # unexpected
            ]
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()

        assert any(
            "random_test_data" in w or "unexpected" in w.lower() for w in report.warnings
        )


class TestSampleValidation:
    """Tests for document sampling and validation"""

    @pytest.mark.asyncio
    async def test_sample_validation_reports_issues(self, mock_db):
        """Document validation issues appear in warnings"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # Set up bible_texts with a document missing required fields
        mock_db._collection_cache["bible_texts"] = AsyncMock()
        mock_db._collection_cache["bible_texts"].index_information = AsyncMock(
            return_value={
                "_id_": {"key": [("_id", 1)]},
                "verse_lookup": {},
                "language_type_filter": {},
                "book_type_filter": {},
            }
        )
        # Return a document missing required fields
        mock_db._collection_cache["bible_texts"].aggregate = MagicMock(
            return_value=AsyncIterator(
                [
                    {
                        "_id": "123",
                        "language_code": "test",
                    }  # missing book_code, chapter, etc.
                ]
            )
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()

        # Should have warnings about missing required fields
        assert len(report.warnings) > 0

    @pytest.mark.asyncio
    async def test_empty_collection_no_crash(self, mock_db):
        """Handles empty collections gracefully"""
        from utils.schema_enforcer.enforcer import SchemaEnforcer

        # dictionaries returns no documents
        mock_db._collection_cache["dictionaries"] = AsyncMock()
        mock_db._collection_cache["dictionaries"].index_information = AsyncMock(
            return_value={"_id_": {"key": [("_id", 1)]}, "dict_lookup": {}}
        )
        mock_db._collection_cache["dictionaries"].aggregate = MagicMock(
            return_value=AsyncIterator([])
        )
        mock_db._collection_cache["dictionaries"].count_documents = AsyncMock(
            return_value=0
        )

        enforcer = SchemaEnforcer(mock_db, dry_run=True)
        report = await enforcer.enforce()  # Should not raise
        # Just verify it completes without error
        assert report is not None
