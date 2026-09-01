"""
Tests for mcp_server/tools/memories.py — 4 read-only memory tools.

Run with: pytest tests/unit/mcp_server/test_memories_tools.py -v

Data setup (from conftest):
  - heb: 5 language_notes (sorted by updated_at: note-1 most recent)
  - heb: 5 correction_log entries (3 bible_verse, 1 dictionary_entry, 1 grammar_category)
  - english: language exists but has no notes doc or correction_log entries
  - bughotu: language exists but has no notes doc or correction_log entries
"""

import pytest


# =============================================================================
# list_language_notes
# =============================================================================


class TestListLanguageNotes:
    """Tests for list_language_notes tool."""

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_mcp_db):
        """Returns notes for a language with correct shape."""
        from mcp_server.tools.memories import list_language_notes

        result = await list_language_notes(mock_mcp_db, "heb")

        assert "notes" in result
        assert "count" in result
        assert "total" in result
        assert "language_code" in result
        assert result["language_code"] == "heb"
        assert result["total"] == 5
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_respects_limit(self, mock_mcp_db):
        """Limit parameter caps notes returned, total reflects full count."""
        from mcp_server.tools.memories import list_language_notes

        result = await list_language_notes(mock_mcp_db, "heb", limit=3)

        assert result["count"] == 3
        assert result["total"] == 5
        assert len(result["notes"]) == 3

    @pytest.mark.asyncio
    async def test_sort_order_updated_at_desc(self, mock_mcp_db):
        """Notes returned sorted by updated_at DESC (most recently modified first)."""
        from mcp_server.tools.memories import list_language_notes

        result = await list_language_notes(mock_mcp_db, "heb")

        notes = result["notes"]
        assert len(notes) >= 2
        # note-1 has updated_at 2024-03-01 (most recent), should be first
        assert notes[0]["id"] == "note-1"
        # note-2 has updated_at 2024-02-01, should be second
        assert notes[1]["id"] == "note-2"

    @pytest.mark.asyncio
    async def test_empty_language_no_notes_doc(self, mock_mcp_db):
        """Language with no notes document returns empty array, not error."""
        from mcp_server.tools.memories import list_language_notes

        result = await list_language_notes(mock_mcp_db, "english")

        assert "error" not in result
        assert result["notes"] == []
        assert result["total"] == 0
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_invalid_language_returns_error(self, mock_mcp_db):
        """Nonexistent language returns error_response, not raise."""
        from mcp_server.tools.memories import list_language_notes

        result = await list_language_notes(mock_mcp_db, "nonexistent_lang")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_limit_clamped_at_100(self, mock_mcp_db):
        """Requesting limit > 100 is clamped silently."""
        from mcp_server.tools.memories import list_language_notes

        # With only 5 notes, clamping to 100 still returns all 5
        result = await list_language_notes(mock_mcp_db, "heb", limit=200)

        assert "error" not in result
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_limit_below_1_defaults_to_50(self, mock_mcp_db):
        """Requesting limit < 1 defaults to 50."""
        from mcp_server.tools.memories import list_language_notes

        result = await list_language_notes(mock_mcp_db, "heb", limit=0)

        assert "error" not in result
        assert result["count"] == 5  # only 5 notes, well under default of 50

    @pytest.mark.asyncio
    async def test_language_code_normalization(self, mock_mcp_db):
        """language_code with hyphens/uppercase is normalized before query."""
        from mcp_server.tools.memories import list_language_notes

        # "HEB" should normalize to "heb" and find the language
        result = await list_language_notes(mock_mcp_db, "HEB")

        assert "error" not in result
        assert result["total"] == 5


# =============================================================================
# search_language_notes
# =============================================================================


class TestSearchLanguageNotes:
    """Tests for search_language_notes tool."""

    @pytest.mark.asyncio
    async def test_substring_match(self, mock_mcp_db):
        """Returns only notes matching the search term."""
        from mcp_server.tools.memories import search_language_notes

        # "gender" appears in note-2 text only
        result = await search_language_notes(mock_mcp_db, "heb", "gender")

        assert "error" not in result
        assert result["total"] == 1
        assert result["count"] == 1
        assert result["notes"][0]["id"] == "note-2"

    @pytest.mark.asyncio
    async def test_case_insensitive(self, mock_mcp_db):
        """Search is case-insensitive."""
        from mcp_server.tools.memories import search_language_notes

        # "GENDER" should match note-2 containing "gender"
        result_upper = await search_language_notes(mock_mcp_db, "heb", "GENDER")
        result_lower = await search_language_notes(mock_mcp_db, "heb", "gender")

        assert result_upper["total"] == result_lower["total"] == 1

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(self, mock_mcp_db):
        """Search with no matches returns empty array, not error."""
        from mcp_server.tools.memories import search_language_notes

        result = await search_language_notes(mock_mcp_db, "heb", "xyznonexistentterm")

        assert "error" not in result
        assert result["notes"] == []
        assert result["total"] == 0
        assert result["search_term"] == "xyznonexistentterm"

    @pytest.mark.asyncio
    async def test_respects_limit(self, mock_mcp_db):
        """Limit caps results; total reflects all matching notes."""
        from mcp_server.tools.memories import search_language_notes

        # All 5 notes contain letters, so broad search returns all
        result = await search_language_notes(mock_mcp_db, "heb", "e", limit=2)

        assert result["count"] == 2
        assert result["total"] >= 2  # at least 2 notes contain "e"

    @pytest.mark.asyncio
    async def test_empty_search_term_returns_all(self, mock_mcp_db):
        """Empty search_term returns all notes (same as list_language_notes)."""
        from mcp_server.tools.memories import search_language_notes

        result = await search_language_notes(mock_mcp_db, "heb", "")

        assert "error" not in result
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_invalid_language_returns_error(self, mock_mcp_db):
        """Nonexistent language returns error_response."""
        from mcp_server.tools.memories import search_language_notes

        result = await search_language_notes(mock_mcp_db, "nonexistent_lang", "term")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_response_includes_search_term(self, mock_mcp_db):
        """Response echoes back the search_term."""
        from mcp_server.tools.memories import search_language_notes

        result = await search_language_notes(mock_mcp_db, "heb", "masculine")

        assert result["search_term"] == "masculine"

    @pytest.mark.asyncio
    async def test_multiple_matches_sorted_desc(self, mock_mcp_db):
        """Multiple matches sorted by updated_at DESC."""
        from mcp_server.tools.memories import search_language_notes

        # "noun" appears in note-2 ("gender"), note-3 ("masculine"/"feminine"), note-5 ("noun")
        result = await search_language_notes(mock_mcp_db, "heb", "noun")

        notes = result["notes"]
        assert len(notes) >= 2
        # Verify descending updated_at order
        for i in range(len(notes) - 1):
            assert (notes[i].get("updated_at") or "") >= (
                notes[i + 1].get("updated_at") or ""
            )

    @pytest.mark.asyncio
    async def test_match_in_title_only(self, mock_mcp_db):
        """Search hits a note whose unique term appears in title but not body."""
        from mcp_server.tools.memories import search_language_notes

        # "telicity" appears only in bn-1.title
        result = await search_language_notes(mock_mcp_db, "bughotu", "telicity")

        assert "error" not in result
        assert result["total"] == 1
        assert result["notes"][0]["id"] == "bn-1"

    @pytest.mark.asyncio
    async def test_match_in_text_only(self, mock_mcp_db):
        """Search hits a note whose unique term appears in body but not title."""
        from mcp_server.tools.memories import search_language_notes

        # "prefixal" appears only in bn-3.text
        result = await search_language_notes(mock_mcp_db, "bughotu", "prefixal")

        assert "error" not in result
        assert result["total"] == 1
        assert result["notes"][0]["id"] == "bn-3"

    @pytest.mark.asyncio
    async def test_match_in_both_fields_dedups(self, mock_mcp_db):
        """A note whose term appears in both title and text is returned once."""
        from mcp_server.tools.memories import search_language_notes

        # "aspect" appears in bn-2.title AND bn-2.text — must dedupe.
        # It also appears in bn-1.text ("Aspect particles..."), so total expected = 2.
        result = await search_language_notes(mock_mcp_db, "bughotu", "aspect")

        assert "error" not in result
        matched_ids = [n["id"] for n in result["notes"]]
        assert matched_ids.count("bn-2") == 1, "bn-2 must appear exactly once"
        assert set(matched_ids) == {"bn-1", "bn-2"}
        assert result["total"] == 2


# =============================================================================
# list_correction_log
# =============================================================================


class TestListCorrectionLog:
    """Tests for list_correction_log tool."""

    @pytest.mark.asyncio
    async def test_all_entries_returned(self, mock_mcp_db):
        """Returns all entries for a language with correct shape."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "heb")

        assert "entries" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result
        assert result["total"] == 5
        assert result["page"] == 1

    @pytest.mark.asyncio
    async def test_entries_sorted_created_at_desc(self, mock_mcp_db):
        """Entries sorted by created_at DESC (newest first)."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "heb")

        entries = result["entries"]
        assert len(entries) >= 2
        # corr-1 created_at 2024-03-01 should be first
        assert entries[0]["id"] == "corr-1"
        assert entries[1]["id"] == "corr-2"

    @pytest.mark.asyncio
    async def test_filter_by_content_type(self, mock_mcp_db):
        """content_type filter returns only matching entries."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(
            mock_mcp_db, "heb", content_type="dictionary_entry"
        )

        assert result["total"] == 1
        assert result["entries"][0]["content_type"] == "dictionary_entry"
        assert result["content_type"] == "dictionary_entry"

    @pytest.mark.asyncio
    async def test_pagination(self, mock_mcp_db):
        """Pagination: page 1 and page 2 return different entries."""
        from mcp_server.tools.memories import list_correction_log

        page1 = await list_correction_log(mock_mcp_db, "heb", page=1, page_size=2)
        page2 = await list_correction_log(mock_mcp_db, "heb", page=2, page_size=2)

        assert len(page1["entries"]) == 2
        assert len(page2["entries"]) == 2
        # Pages contain different entries
        page1_ids = {e["id"] for e in page1["entries"]}
        page2_ids = {e["id"] for e in page2["entries"]}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_page_beyond_total_returns_empty(self, mock_mcp_db):
        """Page beyond total_pages returns empty entries, correct total."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "heb", page=999, page_size=50)

        assert result["entries"] == []
        assert result["total"] == 5
        assert result["page"] == 999

    @pytest.mark.asyncio
    async def test_empty_language_returns_empty(self, mock_mcp_db):
        """Language with no correction entries returns empty array, not error."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "english")

        assert "error" not in result
        assert result["entries"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_content_type_returns_error(self, mock_mcp_db):
        """Invalid content_type returns error_response."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(
            mock_mcp_db, "heb", content_type="invalid_type"
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_page_less_than_1_returns_error(self, mock_mcp_db):
        """page < 1 returns error_response."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "heb", page=0)

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_invalid_language_returns_error(self, mock_mcp_db):
        """Nonexistent language returns error_response."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "nonexistent_lang")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_total_pages_calculated_correctly(self, mock_mcp_db):
        """total_pages = ceil(total / page_size)."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "heb", page_size=2)

        # 5 entries / 2 per page = 3 pages
        assert result["total_pages"] == 3

    @pytest.mark.asyncio
    async def test_page_size_clamped_at_100(self, mock_mcp_db):
        """page_size > 100 is clamped to 100."""
        from mcp_server.tools.memories import list_correction_log

        result = await list_correction_log(mock_mcp_db, "heb", page_size=500)

        assert "error" not in result
        assert result["page_size"] == 100


# =============================================================================
# search_correction_log
# =============================================================================


class TestSearchCorrectionLog:
    """Tests for search_correction_log tool."""

    @pytest.mark.asyncio
    async def test_search_across_original_text(self, mock_mcp_db):
        """Finds entries where search_term is in original_text."""
        from mcp_server.tools.memories import search_correction_log

        # "beginning" appears in corr-1 original_text
        result = await search_correction_log(mock_mcp_db, "heb", "beginning")

        assert "error" not in result
        assert result["total"] >= 1
        matched_ids = {e["id"] for e in result["entries"]}
        assert "corr-1" in matched_ids

    @pytest.mark.asyncio
    async def test_search_across_what_was_wrong(self, mock_mcp_db):
        """Finds entries where search_term is in what_was_wrong."""
        from mcp_server.tools.memories import search_correction_log

        # "formless" appears in corr-3 what_was_wrong
        result = await search_correction_log(mock_mcp_db, "heb", "formless")

        assert result["total"] >= 1
        matched_ids = {e["id"] for e in result["entries"]}
        assert "corr-3" in matched_ids

    @pytest.mark.asyncio
    async def test_search_across_correction(self, mock_mcp_db):
        """Finds entries where search_term is in correction field."""
        from mcp_server.tools.memories import search_correction_log

        # "phonemes" appears in corr-4 correction
        result = await search_correction_log(mock_mcp_db, "heb", "phonemes")

        assert result["total"] >= 1
        matched_ids = {e["id"] for e in result["entries"]}
        assert "corr-4" in matched_ids

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, mock_mcp_db):
        """Search is case-insensitive."""
        from mcp_server.tools.memories import search_correction_log

        result_lower = await search_correction_log(mock_mcp_db, "heb", "beginning")
        result_upper = await search_correction_log(mock_mcp_db, "heb", "BEGINNING")

        assert result_lower["total"] == result_upper["total"]

    @pytest.mark.asyncio
    async def test_filter_and_search_combined(self, mock_mcp_db):
        """content_type filter combined with search term returns correct subset."""
        from mcp_server.tools.memories import search_correction_log

        # "missing" appears in multiple entries, but only 2 are bible_verse
        result = await search_correction_log(
            mock_mcp_db, "heb", "missing", content_type="bible_verse"
        )

        assert "error" not in result
        for entry in result["entries"]:
            assert entry["content_type"] == "bible_verse"

    @pytest.mark.asyncio
    async def test_regex_metacharacters_escaped(self, mock_mcp_db):
        """Regex metacharacters in search_term are treated as literals (re.escape)."""
        from mcp_server.tools.memories import search_correction_log

        # "." would match any char without escaping; should find nothing with literal "."
        # This just verifies no exception is raised (correct behavior: escaped search)
        result = await search_correction_log(mock_mcp_db, "heb", "verb+suffix")

        assert "error" not in result
        assert result["total"] == 0  # no entries contain literal "verb+suffix"

    @pytest.mark.asyncio
    async def test_limit_enforcement(self, mock_mcp_db):
        """limit caps results returned; total reflects all matches."""
        from mcp_server.tools.memories import search_correction_log

        # "the" appears in several entries; limit to 2
        result = await search_correction_log(mock_mcp_db, "heb", "the", limit=2)

        assert result["count"] <= 2
        assert result["total"] >= result["count"]

    @pytest.mark.asyncio
    async def test_empty_search_term_returns_all(self, mock_mcp_db):
        """Empty search_term returns all corrections (optionally filtered by type)."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(mock_mcp_db, "heb", "")

        assert "error" not in result
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_empty_search_with_content_type_filter(self, mock_mcp_db):
        """Empty search + content_type filter returns all entries of that type."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(
            mock_mcp_db, "heb", "", content_type="bible_verse"
        )

        assert "error" not in result
        assert result["total"] == 3
        for entry in result["entries"]:
            assert entry["content_type"] == "bible_verse"

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(self, mock_mcp_db):
        """Search with no matches returns empty array, not error."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(mock_mcp_db, "heb", "xyznonexistentterm")

        assert "error" not in result
        assert result["entries"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_content_type_returns_error(self, mock_mcp_db):
        """Invalid content_type returns error_response."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(
            mock_mcp_db, "heb", "term", content_type="invalid_type"
        )

        assert "error" in result
        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_invalid_language_returns_error(self, mock_mcp_db):
        """Nonexistent language returns error_response."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(mock_mcp_db, "nonexistent_lang", "term")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_limit_clamped_at_100(self, mock_mcp_db):
        """limit > 100 is clamped silently."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(mock_mcp_db, "heb", "", limit=500)

        assert "error" not in result
        # count won't exceed total (5 entries)
        assert result["count"] <= 5

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_mcp_db):
        """Response includes all required fields."""
        from mcp_server.tools.memories import search_correction_log

        result = await search_correction_log(mock_mcp_db, "heb", "test")

        assert "language_code" in result
        assert "search_term" in result
        assert "content_type" in result
        assert "entries" in result
        assert "count" in result
        assert "total" in result
        assert result["language_code"] == "heb"
        assert result["search_term"] == "test"
