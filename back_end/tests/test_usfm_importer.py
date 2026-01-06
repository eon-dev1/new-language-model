# tests/test_usfm_importer.py
"""Tests for USFM MongoDB import functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from datetime import datetime
import tempfile
import os

from utils.usfm_parser.usfm_importer import (
    ImportResult,
    _verse_to_document,
    import_usfm_to_mongodb,
    import_usfm_directory_to_mongodb,
)
from utils.usfm_parser.usfm_parser import ParsedVerse


# Sample USFM content for testing
SAMPLE_USFM = r"""\id GEN
\h Genesis
\c 1
\v 1 \w In the beginning|strong="H7225"\w* God created the heavens and the earth.
\v 2 Now the earth was without shape and empty.
"""


class TestImportResult:
    """Test the ImportResult dataclass."""

    def test_empty_result(self):
        """Empty result should have zero counts."""
        result = ImportResult()
        assert result.verses_imported == 0
        assert result.verses_updated == 0
        assert result.books_processed == 0
        assert result.total_processed == 0
        assert not result.success

    def test_result_with_imports(self):
        """Result with imports should be successful."""
        result = ImportResult(verses_imported=10, books_processed=1)
        assert result.total_processed == 10
        assert result.success

    def test_result_with_updates(self):
        """Result with updates should be successful."""
        result = ImportResult(verses_updated=5, books_processed=1)
        assert result.total_processed == 5
        assert result.success

    def test_result_with_both(self):
        """Result with both imports and updates."""
        result = ImportResult(verses_imported=10, verses_updated=5, books_processed=2)
        assert result.total_processed == 15
        assert result.success


class TestVerseToDocument:
    """Test the _verse_to_document helper function."""

    @pytest.fixture
    def sample_verse(self):
        """Create a sample ParsedVerse for testing."""
        return ParsedVerse(
            book_code="genesis",
            book_name="Genesis",
            usfm_code="GEN",
            chapter=1,
            verse=1,
            raw_text=r'\w In the beginning|strong="H7225"\w*',
            clean_text="In the beginning"
        )

    def test_english_verse_document(self, sample_verse):
        """English verses should populate english_text field."""
        doc = _verse_to_document(sample_verse, "english", "human")

        assert doc["language_code"] == "english"
        assert doc["book_code"] == "genesis"
        assert doc["chapter"] == 1
        assert doc["verse"] == 1
        assert doc["translation_type"] == "human"
        assert doc["english_text"] == "In the beginning"
        assert doc["translated_text"] == ""

    def test_non_english_verse_document(self, sample_verse):
        """Non-English verses should populate translated_text field."""
        doc = _verse_to_document(sample_verse, "kope", "human")

        assert doc["language_code"] == "kope"
        assert doc["english_text"] == ""
        assert doc["translated_text"] == "In the beginning"

    def test_ai_translation_type(self, sample_verse):
        """Should handle AI translation type."""
        doc = _verse_to_document(sample_verse, "english", "ai")
        assert doc["translation_type"] == "ai"

    def test_document_has_timestamp(self, sample_verse):
        """Document should have updated_at timestamp."""
        doc = _verse_to_document(sample_verse, "english", "human")
        assert "updated_at" in doc
        assert isinstance(doc["updated_at"], datetime)


class TestImportUSFMToMongoDB:
    """Test the import_usfm_to_mongodb function."""

    @pytest.fixture
    def temp_usfm_file(self):
        """Create a temporary USFM file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.usfm', delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_USFM)
            temp_path = f.name
        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.fixture
    def mock_connector(self):
        """Create a mock MongoDB connector."""
        connector = MagicMock()
        connector.connect = AsyncMock()
        connector.disconnect = AsyncMock()

        # Mock database and collection
        mock_collection = MagicMock()
        mock_bulk_result = MagicMock()
        mock_bulk_result.upserted_count = 2
        mock_bulk_result.modified_count = 0
        mock_collection.bulk_write = AsyncMock(return_value=mock_bulk_result)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        connector.get_database = MagicMock(return_value=mock_db)

        return connector

    @pytest.mark.asyncio
    async def test_import_single_file(self, temp_usfm_file, mock_connector):
        """Should import a single USFM file."""
        result = await import_usfm_to_mongodb(
            temp_usfm_file,
            language_code="english",
            translation_type="human",
            connector=mock_connector
        )

        assert result.books_processed == 1
        assert result.verses_imported == 2  # Mocked to return 2
        assert result.success

    @pytest.mark.asyncio
    async def test_import_file_not_found(self, mock_connector):
        """Should handle missing file gracefully."""
        result = await import_usfm_to_mongodb(
            "/nonexistent/file.usfm",
            connector=mock_connector
        )

        assert result.books_processed == 0
        assert len(result.errors) > 0
        assert not result.success

    @pytest.mark.asyncio
    async def test_import_creates_connection_if_none(self, temp_usfm_file):
        """Should create connector if none provided."""
        with patch('db_connector.connection.MongoDBConnector') as MockConnector:
            mock_connector = MagicMock()
            mock_connector.connect = AsyncMock()
            mock_connector.disconnect = AsyncMock()

            mock_collection = MagicMock()
            mock_bulk_result = MagicMock()
            mock_bulk_result.upserted_count = 2
            mock_bulk_result.modified_count = 0
            mock_collection.bulk_write = AsyncMock(return_value=mock_bulk_result)

            mock_db = MagicMock()
            mock_db.__getitem__ = MagicMock(return_value=mock_collection)
            mock_connector.get_database = MagicMock(return_value=mock_db)

            MockConnector.return_value = mock_connector

            result = await import_usfm_to_mongodb(temp_usfm_file)

            # Should have created and closed connection
            mock_connector.connect.assert_called_once()
            mock_connector.disconnect.assert_called_once()


class TestImportUSFMDirectoryToMongoDB:
    """Test the import_usfm_directory_to_mongodb function."""

    @pytest.fixture
    def temp_usfm_directory(self):
        """Create a temporary directory with USFM files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create Genesis file
            gen_path = Path(temp_dir) / "01-GEN.usfm"
            with open(gen_path, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_USFM)

            # Create another file
            mat_content = SAMPLE_USFM.replace("GEN", "MAT").replace("Genesis", "Matthew")
            mat_path = Path(temp_dir) / "40-MAT.usfm"
            with open(mat_path, 'w', encoding='utf-8') as f:
                f.write(mat_content)

            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_import_directory(self, temp_usfm_directory):
        """Should import all files in directory."""
        with patch('db_connector.connection.MongoDBConnector') as MockConnector:
            mock_connector = MagicMock()
            mock_connector.connect = AsyncMock()
            mock_connector.disconnect = AsyncMock()

            mock_collection = MagicMock()
            mock_bulk_result = MagicMock()
            mock_bulk_result.upserted_count = 2
            mock_bulk_result.modified_count = 0
            mock_collection.bulk_write = AsyncMock(return_value=mock_bulk_result)

            mock_db = MagicMock()
            mock_db.__getitem__ = MagicMock(return_value=mock_collection)
            mock_connector.get_database = MagicMock(return_value=mock_db)

            MockConnector.return_value = mock_connector

            result = await import_usfm_directory_to_mongodb(temp_usfm_directory)

            assert result.books_processed == 2  # Two files
            assert result.verses_imported == 4  # 2 per file
            assert result.success

    @pytest.mark.asyncio
    async def test_directory_not_found(self):
        """Should handle missing directory."""
        result = await import_usfm_directory_to_mongodb("/nonexistent/directory")

        assert result.books_processed == 0
        assert len(result.errors) > 0
        assert not result.success

    @pytest.mark.asyncio
    async def test_empty_directory(self):
        """Should handle empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await import_usfm_directory_to_mongodb(temp_dir)
            assert len(result.errors) > 0
            assert not result.success


class TestBulkWriteOperations:
    """Test that bulk write operations are constructed correctly."""

    @pytest.fixture
    def temp_usfm_file(self):
        """Create a temporary USFM file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.usfm', delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_USFM)
            temp_path = f.name
        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_upsert_operations(self, temp_usfm_file):
        """Should create upsert operations for each verse."""
        with patch('db_connector.connection.MongoDBConnector') as MockConnector:
            mock_connector = MagicMock()
            mock_connector.connect = AsyncMock()
            mock_connector.disconnect = AsyncMock()

            mock_collection = MagicMock()
            mock_bulk_result = MagicMock()
            mock_bulk_result.upserted_count = 2
            mock_bulk_result.modified_count = 0
            mock_collection.bulk_write = AsyncMock(return_value=mock_bulk_result)

            mock_db = MagicMock()
            mock_db.__getitem__ = MagicMock(return_value=mock_collection)
            mock_connector.get_database = MagicMock(return_value=mock_db)

            MockConnector.return_value = mock_connector

            await import_usfm_to_mongodb(temp_usfm_file)

            # Verify bulk_write was called
            mock_collection.bulk_write.assert_called_once()

            # Get the operations passed to bulk_write
            call_args = mock_collection.bulk_write.call_args
            operations = call_args[0][0]

            # Should have 2 operations (2 verses in sample)
            assert len(operations) == 2


class TestLanguageCodeHandling:
    """Test language code handling in imports."""

    @pytest.fixture
    def temp_usfm_file(self):
        """Create a temporary USFM file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.usfm', delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_USFM)
            temp_path = f.name
        yield Path(temp_path)
        os.unlink(temp_path)

    def test_english_text_field_for_english(self):
        """English content should go to english_text field."""
        verse = ParsedVerse(
            book_code="genesis",
            book_name="Genesis",
            usfm_code="GEN",
            chapter=1,
            verse=1,
            raw_text="raw",
            clean_text="In the beginning"
        )
        doc = _verse_to_document(verse, "english", "human")

        assert doc["english_text"] == "In the beginning"
        assert doc["translated_text"] == ""

    def test_translated_text_field_for_other_languages(self):
        """Non-English content should go to translated_text field."""
        verse = ParsedVerse(
            book_code="genesis",
            book_name="Genesis",
            usfm_code="GEN",
            chapter=1,
            verse=1,
            raw_text="raw",
            clean_text="Au commencement"  # French translation
        )
        doc = _verse_to_document(verse, "french", "human")

        assert doc["english_text"] == ""
        assert doc["translated_text"] == "Au commencement"