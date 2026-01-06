"""
Tests for mcp_server/tools/bible.py - Bible tools.

TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/mcp_server/test_bible.py -v
"""

import pytest


class TestListBibleBooks:
    """Tests for list_bible_books tool"""

    @pytest.mark.asyncio
    async def test_list_bible_books_returns_books(self, mock_mcp_db):
        """Returns books for a language"""
        from mcp_server.tools.bible import list_bible_books

        result = await list_bible_books(mock_mcp_db, "english")

        assert "books" in result
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_list_bible_books_response_shape(self, mock_mcp_db):
        """Each book has expected fields"""
        from mcp_server.tools.bible import list_bible_books

        result = await list_bible_books(mock_mcp_db, "english")

        for book in result["books"]:
            assert "code" in book
            assert "name" in book
            assert "chapter_count" in book
            assert "testament" in book
            assert "book_order" in book

    @pytest.mark.asyncio
    async def test_list_bible_books_filters_by_translation_type(self, mock_mcp_db):
        """Filters books by translation type when specified"""
        from mcp_server.tools.bible import list_bible_books

        result = await list_bible_books(mock_mcp_db, "heb", translation_type="human")

        # All returned books should be human translations
        for book in result["books"]:
            assert book.get("translation_type") == "human"

    @pytest.mark.asyncio
    async def test_list_bible_books_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.bible import list_bible_books

        result = await list_bible_books(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_bible_books_empty_language(self, mock_mcp_db):
        """Returns empty list for language with no books"""
        from mcp_server.tools.bible import list_bible_books

        # English exists but let's query with a type that has no books
        result = await list_bible_books(mock_mcp_db, "english", translation_type="ai")

        assert result["books"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_list_bible_books_sorted_by_canonical_order(self, mock_mcp_db):
        """Books are sorted by canonical order (1-66)"""
        from mcp_server.tools.bible import list_bible_books

        result = await list_bible_books(mock_mcp_db, "heb")

        if len(result["books"]) > 1:
            orders = [b["book_order"] for b in result["books"]]
            assert orders == sorted(orders)


class TestGetChapter:
    """Tests for get_chapter tool"""

    @pytest.mark.asyncio
    async def test_get_chapter_returns_verses(self, mock_mcp_db):
        """Returns verses for a chapter"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "genesis", 1)

        assert "verses" in result
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_get_chapter_verse_shape(self, mock_mcp_db):
        """Each verse has expected fields"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "genesis", 1)

        for verse in result["verses"]:
            assert "verse" in verse
            assert "text" in verse  # Normalized field name

    @pytest.mark.asyncio
    async def test_get_chapter_english_no_human_verified(self, mock_mcp_db):
        """English verses don't have human_verified field"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "genesis", 1)

        for verse in result["verses"]:
            assert "human_verified" not in verse

    @pytest.mark.asyncio
    async def test_get_chapter_non_english_has_human_verified(self, mock_mcp_db):
        """Non-English verses have human_verified field"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "heb", "genesis", 1)

        for verse in result["verses"]:
            assert "human_verified" in verse

    @pytest.mark.asyncio
    async def test_get_chapter_sorted_by_verse_number(self, mock_mcp_db):
        """Verses are sorted by verse number"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "genesis", 1)

        if len(result["verses"]) > 1:
            numbers = [v["verse"] for v in result["verses"]]
            assert numbers == sorted(numbers)

    @pytest.mark.asyncio
    async def test_get_chapter_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "nonexistent", "genesis", 1)

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_chapter_book_not_found(self, mock_mcp_db):
        """Returns error for nonexistent book"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "nonexistent_book", 1)

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_chapter_chapter_not_found(self, mock_mcp_db):
        """Returns error for nonexistent chapter"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "genesis", 999)

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_chapter_normalizes_book_code(self, mock_mcp_db):
        """Handles uppercase book codes"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(mock_mcp_db, "english", "GENESIS", 1)

        # Should work, not error
        assert "verses" in result or "error" not in result

    @pytest.mark.asyncio
    async def test_get_chapter_with_translation_type(self, mock_mcp_db):
        """Filters by translation type when specified"""
        from mcp_server.tools.bible import get_chapter

        result = await get_chapter(
            mock_mcp_db, "heb", "genesis", 1, translation_type="human"
        )

        assert "verses" in result


class TestGetBibleChunk:
    """Tests for get_bible_chunk tool (paginated verse access)"""

    @pytest.mark.asyncio
    async def test_get_bible_chunk_returns_verses(self, mock_mcp_db):
        """Returns paginated verses"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(mock_mcp_db, "english")

        assert "verses" in result
        assert "total" in result
        assert "offset" in result
        assert "limit" in result

    @pytest.mark.asyncio
    async def test_get_bible_chunk_respects_limit(self, mock_mcp_db):
        """Returns at most 'limit' verses"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(mock_mcp_db, "english", limit=1)

        assert len(result["verses"]) <= 1

    @pytest.mark.asyncio
    async def test_get_bible_chunk_respects_offset(self, mock_mcp_db):
        """Skips 'offset' verses"""
        from mcp_server.tools.bible import get_bible_chunk

        # Get first chunk
        first = await get_bible_chunk(mock_mcp_db, "english", offset=0, limit=1)
        # Get second chunk
        second = await get_bible_chunk(mock_mcp_db, "english", offset=1, limit=1)

        if first["verses"] and second["verses"]:
            assert first["verses"][0] != second["verses"][0]

    @pytest.mark.asyncio
    async def test_get_bible_chunk_filters_by_book(self, mock_mcp_db):
        """Filters by book when specified"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(mock_mcp_db, "english", book_code="genesis")

        for verse in result["verses"]:
            assert verse["book_code"] == "genesis"

    @pytest.mark.asyncio
    async def test_get_bible_chunk_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_bible_chunk_includes_location_info(self, mock_mcp_db):
        """Each verse includes book, chapter, verse info"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(mock_mcp_db, "english")

        for verse in result["verses"]:
            assert "book_code" in verse
            assert "chapter" in verse
            assert "verse" in verse
            assert "text" in verse


class TestGetBibleChunkSaveToFile:
    """Tests for get_bible_chunk save_to_file feature"""

    @pytest.mark.asyncio
    async def test_save_to_file_returns_file_info(self, mock_mcp_db, tmp_path, monkeypatch):
        """When save_to_file provided, returns file path instead of data"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_bible_chunk

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_bible_chunk(
            mock_mcp_db, "english", save_to_file="test_output"
        )

        # Should return file info, not verses
        assert "saved_to" in result
        assert "record_count" in result
        assert "filename" in result
        assert "verses" not in result

    @pytest.mark.asyncio
    async def test_save_to_file_creates_file(self, mock_mcp_db, tmp_path, monkeypatch):
        """File is actually created on disk"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_bible_chunk

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_bible_chunk(
            mock_mcp_db, "english", save_to_file="verses_file"
        )

        assert (tmp_path / "verses_file.json").exists()

    @pytest.mark.asyncio
    async def test_save_to_file_none_returns_data(self, mock_mcp_db):
        """When save_to_file is None, returns data inline (default behavior)"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(mock_mcp_db, "english", save_to_file=None)

        # Should return verses inline
        assert "verses" in result
        assert "saved_to" not in result

    @pytest.mark.asyncio
    async def test_save_to_file_contains_correct_data(
        self, mock_mcp_db, tmp_path, monkeypatch
    ):
        """Saved file contains the verse data"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_bible_chunk

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_bible_chunk(
            mock_mcp_db, "english", save_to_file="data_check"
        )

        saved_file = tmp_path / "data_check.json"
        content = json.loads(saved_file.read_text())

        assert "verses" in content
        assert "total" in content
        assert "offset" in content
        assert "limit" in content

    @pytest.mark.asyncio
    async def test_save_to_file_invalid_name_returns_error(self, mock_mcp_db):
        """Invalid filename returns error response"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(
            mock_mcp_db, "english", save_to_file="invalid file!"
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_save_to_file_record_count_matches_verses(
        self, mock_mcp_db, tmp_path, monkeypatch
    ):
        """record_count matches number of verses"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_bible_chunk

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_bible_chunk(
            mock_mcp_db, "english", limit=2, save_to_file="count_check"
        )

        saved_file = tmp_path / "count_check.json"
        content = json.loads(saved_file.read_text())

        assert result["record_count"] == len(content["verses"])

    @pytest.mark.asyncio
    async def test_save_to_file_with_filters(self, mock_mcp_db, tmp_path, monkeypatch):
        """Filters (book_code, offset, limit) still work with save_to_file"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_bible_chunk

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_bible_chunk(
            mock_mcp_db,
            "english",
            book_code="genesis",
            offset=0,
            limit=1,
            save_to_file="filtered",
        )

        saved_file = tmp_path / "filtered.json"
        content = json.loads(saved_file.read_text())

        # Filters should be applied
        for verse in content["verses"]:
            assert verse["book_code"] == "genesis"

    @pytest.mark.asyncio
    async def test_save_to_file_language_not_found(self, mock_mcp_db):
        """Language validation happens before file save"""
        from mcp_server.tools.bible import get_bible_chunk

        result = await get_bible_chunk(
            mock_mcp_db, "nonexistent", save_to_file="should_not_create"
        )

        assert "error" in result
        assert result["error"]["code"] == "not_found"


class TestSaveBibleBatches:
    """Tests for save_bible_batches tool (batch file saving)"""

    # === Happy Path ===

    @pytest.mark.asyncio
    async def test_saves_single_batch(self, mock_mcp_db, tmp_path, monkeypatch):
        """Saves one batch when start=end"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=5, batch_start=1, batch_end=1
        )

        assert result["batches_saved"] == 1
        assert len(result["files"]) == 1
        assert (tmp_path / result["files"][0]["filename"]).exists()

    @pytest.mark.asyncio
    async def test_saves_multiple_batches(self, mock_mcp_db, tmp_path, monkeypatch):
        """Saves range of batches"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # English has 10 verses, batch_size=4 means 3 batches (4+4+2)
        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=4, batch_start=1, batch_end=3
        )

        assert result["batches_saved"] == 3
        assert len(result["files"]) == 3

    @pytest.mark.asyncio
    async def test_saves_all_batches_when_end_none(self, mock_mcp_db, tmp_path, monkeypatch):
        """batch_end=None saves all available batches"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # English has 10 verses, batch_size=4 means 3 batches
        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=4, batch_end=None
        )

        assert result["batches_saved"] == 3
        assert result["total_batches_available"] == 3

    # === Return Shape ===

    @pytest.mark.asyncio
    async def test_return_shape(self, mock_mcp_db, tmp_path, monkeypatch):
        """Response has expected fields"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=5, batch_end=1
        )

        assert "batches_saved" in result
        assert "files" in result
        assert "verses_saved" in result
        assert "first_batch" in result
        assert "last_batch" in result
        assert "total_batches_available" in result

    @pytest.mark.asyncio
    async def test_file_info_shape(self, mock_mcp_db, tmp_path, monkeypatch):
        """Each file entry has batch, filename, saved_to, record_count"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=5, batch_end=1
        )

        file_info = result["files"][0]
        assert "batch" in file_info
        assert "filename" in file_info
        assert "saved_to" in file_info
        assert "record_count" in file_info

    # === Batch Arithmetic ===

    @pytest.mark.asyncio
    async def test_batch_one_indexed(self, mock_mcp_db, tmp_path, monkeypatch):
        """Batch 1 starts at offset 0 (verse 1), batch 2 at batch_size"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=3, batch_start=1, batch_end=1
        )

        # Read the saved file and check first verse is verse 1
        saved_file = tmp_path / result["files"][0]["filename"]
        content = json.loads(saved_file.read_text())
        assert content["verses"][0]["verse"] == 1

    @pytest.mark.asyncio
    async def test_partial_last_batch(self, mock_mcp_db, tmp_path, monkeypatch):
        """Last batch may have fewer than batch_size verses"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # English has 10 verses, batch_size=4 means batches of 4, 4, 2
        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=4
        )

        # Last batch should have only 2 verses
        last_file = result["files"][-1]
        assert last_file["record_count"] == 2

    @pytest.mark.asyncio
    async def test_sum_record_counts_equals_total(self, mock_mcp_db, tmp_path, monkeypatch):
        """Sum of all file record_counts equals verses_saved"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=4
        )

        total_from_files = sum(f["record_count"] for f in result["files"])
        assert total_from_files == result["verses_saved"]

    # === Filenames ===

    @pytest.mark.asyncio
    async def test_zero_padded_filenames(self, mock_mcp_db, tmp_path, monkeypatch):
        """Filenames use 3-digit zero padding (_001, _002, etc.)"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=5
        )

        assert result["files"][0]["filename"].endswith("_001.json")
        assert result["files"][1]["filename"].endswith("_002.json")

    @pytest.mark.asyncio
    async def test_custom_prefix(self, mock_mcp_db, tmp_path, monkeypatch):
        """Custom filename_prefix is used"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=10, filename_prefix="my_export"
        )

        assert result["files"][0]["filename"] == "my_export_001.json"

    @pytest.mark.asyncio
    async def test_default_prefix(self, mock_mcp_db, tmp_path, monkeypatch):
        """Default prefix is {lang}_batch"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=10
        )

        assert result["files"][0]["filename"].startswith("english_batch_")

    # === Edge Cases ===

    @pytest.mark.asyncio
    async def test_empty_language_returns_zero_batches(self, mock_mcp_db, tmp_path, monkeypatch):
        """Language with 0 verses returns batches_saved=0, files=[]"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # Query with AI translation type which doesn't exist in test data
        result = await save_bible_batches(
            mock_mcp_db, "english", translation_type="ai"
        )

        assert result["batches_saved"] == 0
        assert result["files"] == []
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_batch_end_exceeds_total_clamps(self, mock_mcp_db, tmp_path, monkeypatch):
        """batch_end > total_batches clamps to actual batches"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # English has 10 verses, batch_size=5 means 2 batches. Ask for 100.
        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=5, batch_end=100
        )

        assert result["batches_saved"] == 2
        assert result["last_batch"] == 2

    @pytest.mark.asyncio
    async def test_batch_start_exceeds_total_returns_empty(self, mock_mcp_db, tmp_path, monkeypatch):
        """batch_start > total_batches returns empty result (not error)"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # English has 2 batches with batch_size=5. Ask for batch 10.
        result = await save_bible_batches(
            mock_mcp_db, "english", batch_size=5, batch_start=10
        )

        assert result["batches_saved"] == 0
        assert result["files"] == []
        assert "error" not in result

    # === Error Cases ===

    @pytest.mark.asyncio
    async def test_invalid_range_start_gt_end(self, mock_mcp_db):
        """batch_start > batch_end (explicit) returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(
            mock_mcp_db, "english", batch_start=5, batch_end=3
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_language_not_found(self, mock_mcp_db):
        """Nonexistent language returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_invalid_book_code(self, mock_mcp_db):
        """Invalid book_code returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(
            mock_mcp_db, "english", book_code="invalid book!"
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_invalid_translation_type(self, mock_mcp_db):
        """Invalid translation_type returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(
            mock_mcp_db, "english", translation_type="invalid"
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    # === Parameter Validation ===

    @pytest.mark.asyncio
    async def test_batch_size_zero_returns_error(self, mock_mcp_db):
        """batch_size=0 returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(mock_mcp_db, "english", batch_size=0)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_batch_size_negative_returns_error(self, mock_mcp_db):
        """batch_size=-1 returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(mock_mcp_db, "english", batch_size=-1)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_batch_size_over_500_returns_error(self, mock_mcp_db):
        """batch_size=501 returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(mock_mcp_db, "english", batch_size=501)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_batch_start_zero_returns_error(self, mock_mcp_db):
        """batch_start=0 returns error (1-indexed)"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(mock_mcp_db, "english", batch_start=0)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_batch_start_negative_returns_error(self, mock_mcp_db):
        """batch_start=-1 returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(mock_mcp_db, "english", batch_start=-1)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_filename_prefix_invalid_chars_returns_error(self, mock_mcp_db):
        """filename_prefix with spaces/special chars returns error"""
        from mcp_server.tools.bible import save_bible_batches

        result = await save_bible_batches(
            mock_mcp_db, "english", filename_prefix="bad prefix!"
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    # === Filters ===

    @pytest.mark.asyncio
    async def test_book_filter(self, mock_mcp_db, tmp_path, monkeypatch):
        """book_code filter limits to one book"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await save_bible_batches(
            mock_mcp_db, "english", book_code="genesis", batch_size=10
        )

        # Read saved file and verify all verses are genesis
        saved_file = tmp_path / result["files"][0]["filename"]
        content = json.loads(saved_file.read_text())
        for verse in content["verses"]:
            assert verse["book_code"] == "genesis"

    @pytest.mark.asyncio
    async def test_translation_type_filter(self, mock_mcp_db, tmp_path, monkeypatch):
        """translation_type filter limits to human or ai"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import save_bible_batches

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        # Hebrew has 5 human verses in test data
        result = await save_bible_batches(
            mock_mcp_db, "heb", translation_type="human", batch_size=10
        )

        assert result["verses_saved"] == 5


class TestGetParallelVerses:
    """Tests for get_parallel_verses tool (multi-language comparison)"""

    # === Input Validation ===

    @pytest.mark.asyncio
    async def test_parallel_empty_language_codes_returns_error(self, mock_mcp_db):
        """Empty language_codes returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(mock_mcp_db, [], "genesis", 1)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"
        assert "empty" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_parallel_single_language_returns_error(self, mock_mcp_db):
        """Single language returns error (need 2+ for comparison)"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(mock_mcp_db, ["english"], "genesis", 1)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"
        assert "2" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_parallel_dedup_to_single_returns_error(self, mock_mcp_db):
        """['english', 'English'] deduplicates to 1, returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "English", "ENGLISH"], "genesis", 1
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"
        assert "2" in result["error"]["message"] or "unique" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_parallel_chapter_zero_returns_error(self, mock_mcp_db):
        """chapter=0 returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 0
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"
        assert "chapter" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_parallel_chapter_negative_returns_error(self, mock_mcp_db):
        """chapter=-1 returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", -1
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_parallel_verse_start_zero_returns_error(self, mock_mcp_db):
        """verse_start=0 returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1, verse_start=0
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_parallel_verse_start_exceeds_end_returns_error(self, mock_mcp_db):
        """verse_start > verse_end returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1,
            verse_start=10, verse_end=5
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"
        assert "exceed" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_parallel_language_not_found_returns_error(self, mock_mcp_db):
        """Nonexistent language returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "nonexistent"], "genesis", 1
        )

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_parallel_too_many_languages_returns_error(self, mock_mcp_db):
        """More than 10 languages returns error"""
        from mcp_server.tools.bible import get_parallel_verses

        # Create list of 11 "unique" language codes (will fail on first validation)
        langs = [f"lang{i}" for i in range(11)]
        result = await get_parallel_verses(mock_mcp_db, langs, "genesis", 1)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"
        assert "10" in result["error"]["message"]

    # === Response Shape ===

    @pytest.mark.asyncio
    async def test_parallel_response_shape(self, mock_mcp_db):
        """Response has expected fields"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1, verse_start=1, verse_end=3
        )

        assert "parallel_verses" in result
        assert "languages" in result
        assert "book_code" in result
        assert "chapter" in result
        assert "verse_range" in result
        assert "count" in result
        assert "missing_translations" in result

    @pytest.mark.asyncio
    async def test_parallel_verse_object_shape(self, mock_mcp_db):
        """Each verse object has expected structure"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1, verse_start=1, verse_end=1
        )

        verse = result["parallel_verses"][0]
        assert "book_code" in verse
        assert "chapter" in verse
        assert "verse" in verse
        assert "translations" in verse
        assert isinstance(verse["translations"], dict)

    @pytest.mark.asyncio
    async def test_parallel_translation_object_shape(self, mock_mcp_db):
        """Each translation has text, translation_type, and human_verified (non-English)"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1, verse_start=1, verse_end=1
        )

        verse = result["parallel_verses"][0]

        # English translation
        eng = verse["translations"]["english"]
        assert "text" in eng
        assert "translation_type" in eng
        assert "human_verified" not in eng  # English has no human_verified

        # Hebrew translation
        heb = verse["translations"]["heb"]
        assert "text" in heb
        assert "translation_type" in heb
        assert "human_verified" in heb  # Non-English has human_verified

    # === Happy Path ===

    @pytest.mark.asyncio
    async def test_parallel_two_languages(self, mock_mcp_db):
        """Returns aligned verses for 2 languages"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "bughotu"], "genesis", 1, verse_start=3, verse_end=5
        )

        assert result["count"] == 3
        assert result["languages"] == ["english", "bughotu"]
        assert result["verse_range"] == [3, 5]

        # Each verse should have translations for both languages
        for verse in result["parallel_verses"]:
            assert "english" in verse["translations"]
            assert "bughotu" in verse["translations"]

    @pytest.mark.asyncio
    async def test_parallel_three_languages(self, mock_mcp_db):
        """Returns aligned verses for 3 languages"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb", "bughotu"], "genesis", 1, verse_start=3, verse_end=5
        )

        assert result["count"] == 3
        assert set(result["languages"]) == {"english", "heb", "bughotu"}

    @pytest.mark.asyncio
    async def test_parallel_single_verse(self, mock_mcp_db):
        """verse_start=verse_end returns single verse"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1, verse_start=3, verse_end=3
        )

        assert result["count"] == 1
        assert result["verse_range"] == [3, 3]
        assert result["parallel_verses"][0]["verse"] == 3

    @pytest.mark.asyncio
    async def test_parallel_case_insensitive_languages(self, mock_mcp_db):
        """Language codes are normalized to lowercase"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["ENGLISH", "Heb"], "genesis", 1, verse_start=1, verse_end=2
        )

        assert "error" not in result
        assert result["languages"] == ["english", "heb"]

    @pytest.mark.asyncio
    async def test_parallel_verses_sorted_by_number(self, mock_mcp_db):
        """Verses are sorted by verse number"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1, verse_start=1, verse_end=5
        )

        verse_nums = [v["verse"] for v in result["parallel_verses"]]
        assert verse_nums == sorted(verse_nums)

    # === Translation Priority: Human > AI ===

    @pytest.mark.asyncio
    async def test_parallel_human_preferred_over_ai(self, mock_mcp_db):
        """When both human and AI exist, returns human translation"""
        from mcp_server.tools.bible import get_parallel_verses

        # Bughotu verse 5 has both human and AI translations in test data
        result = await get_parallel_verses(
            mock_mcp_db, ["english", "bughotu"], "genesis", 1, verse_start=5, verse_end=5
        )

        verse5 = result["parallel_verses"][0]
        bughotu_trans = verse5["translations"]["bughotu"]

        # Should return human, not AI
        assert bughotu_trans["translation_type"] == "human"
        assert bughotu_trans["human_verified"] is True
        assert "Human verified" in bughotu_trans["text"]

    @pytest.mark.asyncio
    async def test_parallel_ai_returned_when_only_ai_exists(self, mock_mcp_db):
        """When only AI exists, returns AI translation with correct type"""
        from mcp_server.tools.bible import get_parallel_verses

        # Bughotu verse 3 only has AI translation in test data
        result = await get_parallel_verses(
            mock_mcp_db, ["english", "bughotu"], "genesis", 1, verse_start=3, verse_end=3
        )

        verse3 = result["parallel_verses"][0]
        bughotu_trans = verse3["translations"]["bughotu"]

        # Should return AI
        assert bughotu_trans["translation_type"] == "ai"
        assert bughotu_trans["human_verified"] is False

    @pytest.mark.asyncio
    async def test_parallel_english_always_human(self, mock_mcp_db):
        """English verses always have translation_type=human"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "bughotu"], "genesis", 1, verse_start=1, verse_end=5
        )

        for verse in result["parallel_verses"]:
            if "english" in verse["translations"]:
                assert verse["translations"]["english"]["translation_type"] == "human"

    # === Missing Translations ===

    @pytest.mark.asyncio
    async def test_parallel_missing_translations_tracked(self, mock_mcp_db):
        """Languages with missing verses are tracked in missing_translations"""
        from mcp_server.tools.bible import get_parallel_verses

        # English has 1-10, Bughotu has 3-7
        result = await get_parallel_verses(
            mock_mcp_db, ["english", "bughotu"], "genesis", 1, verse_start=1, verse_end=5
        )

        # Bughotu should be missing verses 1 and 2
        assert "bughotu" in result["missing_translations"]
        assert 1 in result["missing_translations"]["bughotu"]
        assert 2 in result["missing_translations"]["bughotu"]

        # English should have no missing verses for 1-5
        assert "english" not in result["missing_translations"]

    @pytest.mark.asyncio
    async def test_parallel_three_languages_different_gaps(self, mock_mcp_db):
        """Tracks different gaps for each language correctly"""
        from mcp_server.tools.bible import get_parallel_verses

        # English: 1-10, Hebrew: 1-5, Bughotu: 3-7
        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb", "bughotu"], "genesis", 1, verse_start=1, verse_end=7
        )

        missing = result["missing_translations"]

        # English has all verses 1-7
        assert "english" not in missing

        # Hebrew missing 6, 7
        assert "heb" in missing
        assert set(missing["heb"]) == {6, 7}

        # Bughotu missing 1, 2
        assert "bughotu" in missing
        assert set(missing["bughotu"]) == {1, 2}

    @pytest.mark.asyncio
    async def test_parallel_no_missing_when_complete(self, mock_mcp_db):
        """missing_translations is empty when all languages have all verses"""
        from mcp_server.tools.bible import get_parallel_verses

        # Verses 3-5: English has them, Hebrew has them, Bughotu has them
        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb", "bughotu"], "genesis", 1, verse_start=3, verse_end=5
        )

        assert result["missing_translations"] == {}

    @pytest.mark.asyncio
    async def test_parallel_partial_translation_included(self, mock_mcp_db):
        """Verses with partial translations still appear in parallel_verses"""
        from mcp_server.tools.bible import get_parallel_verses

        # Verse 1: English has it, Bughotu doesn't
        result = await get_parallel_verses(
            mock_mcp_db, ["english", "bughotu"], "genesis", 1, verse_start=1, verse_end=1
        )

        assert result["count"] == 1
        verse1 = result["parallel_verses"][0]
        assert "english" in verse1["translations"]
        assert "bughotu" not in verse1["translations"]  # Not present at all

    # === Empty Results ===

    @pytest.mark.asyncio
    async def test_parallel_nonexistent_chapter_returns_empty(self, mock_mcp_db):
        """Chapter that doesn't exist returns empty parallel_verses"""
        from mcp_server.tools.bible import get_parallel_verses

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 999
        )

        assert "error" not in result
        assert result["parallel_verses"] == []
        assert result["count"] == 0

    # === Save to File ===

    @pytest.mark.asyncio
    async def test_parallel_save_to_file_returns_file_info(
        self, mock_mcp_db, tmp_path, monkeypatch
    ):
        """save_to_file returns file info instead of data"""
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_parallel_verses

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1,
            verse_start=1, verse_end=3, save_to_file="parallel_test"
        )

        assert "saved_to" in result
        assert "record_count" in result
        assert "parallel_verses" not in result

    @pytest.mark.asyncio
    async def test_parallel_save_to_file_creates_file(
        self, mock_mcp_db, tmp_path, monkeypatch
    ):
        """File is actually created with correct data"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.bible import get_parallel_verses

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        result = await get_parallel_verses(
            mock_mcp_db, ["english", "heb"], "genesis", 1,
            verse_start=1, verse_end=3, save_to_file="parallel_output"
        )

        saved_file = tmp_path / "parallel_output.json"
        assert saved_file.exists()

        content = json.loads(saved_file.read_text())
        assert "parallel_verses" in content
        assert "languages" in content
