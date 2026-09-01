"""
Tests for mcp_server/tools/dictionary.py - Dictionary tools.

TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/mcp_server/test_dictionary.py -v

Note: Dictionary uses embedded entries[] array pattern.
One doc per (language, translation_type) with entries embedded.
"""

import pytest


class TestListDictionaryEntries:
    """Tests for list_dictionary_entries tool"""

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_returns_entries(self, mock_mcp_db):
        """Returns entries for a language"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb")

        assert "entries" in result
        assert "total" in result
        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_response_shape(self, mock_mcp_db):
        """Each entry has expected fields"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb")

        for entry in result["entries"]:
            assert "word" in entry
            assert "definition" in entry
            assert "part_of_speech" in entry

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_returns_entries_for_language(self, mock_mcp_db):
        """Returns entries for the language"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb")

        assert "entries" in result

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_pagination(self, mock_mcp_db):
        """Supports offset and limit for pagination"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        # Get all entries
        all_result = await list_dictionary_entries(mock_mcp_db, "heb")

        # Get with limit
        limited = await list_dictionary_entries(mock_mcp_db, "heb", limit=1)

        assert len(limited["entries"]) <= 1
        assert limited["offset"] == 0
        assert limited["limit"] == 1

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_offset(self, mock_mcp_db):
        """Offset skips entries"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        first = await list_dictionary_entries(mock_mcp_db, "heb", offset=0, limit=1)
        second = await list_dictionary_entries(mock_mcp_db, "heb", offset=1, limit=1)

        if first["entries"] and second["entries"]:
            assert first["entries"][0]["word"] != second["entries"][0]["word"]

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_empty_dictionary(self, mock_mcp_db):
        """Returns empty list for language with no entries"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        # English exists but has no dictionary in test data
        result = await list_dictionary_entries(mock_mcp_db, "english")

        assert result["entries"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_dictionary_entries_with_search(self, mock_mcp_db):
        """Filters entries by search term"""
        from mcp_server.tools.dictionary import list_dictionary_entries

        result = await list_dictionary_entries(mock_mcp_db, "heb", search="beginning")

        # Should find entry with "beginning" in definition
        if result["entries"]:
            assert any("beginning" in e["definition"].lower() for e in result["entries"])


class TestGetDictionaryEntry:
    """Tests for get_dictionary_entry tool"""

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_exists(self, mock_mcp_db):
        """Returns entry when word exists"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "בראשית")

        assert "word" in result
        assert result["word"] == "בראשית"
        assert "definition" in result

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_not_found(self, mock_mcp_db):
        """Returns error when word doesn't exist"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "nonexistent_word")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_returns_word_field(self, mock_mcp_db):
        """Entry returned has word field"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "בראשית")

        assert "word" in result

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "nonexistent", "word")

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_dictionary_entry_includes_examples(self, mock_mcp_db):
        """Entry includes examples field"""
        from mcp_server.tools.dictionary import get_dictionary_entry

        result = await get_dictionary_entry(mock_mcp_db, "heb", "בראשית")

        assert "examples" in result


class TestUpsertDictionaryEntries:
    """Tests for upsert_dictionary_entries tool"""

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_insert_new(self, mock_mcp_db):
        """Inserts new entries"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        new_entries = [
            {
                "word": "חדש",
                "definition": "new",
                "part_of_speech": "adjective",
            }
        ]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", new_entries
        )

        assert result["created"] >= 1
        assert "total" in result

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_update_existing(self, mock_mcp_db):
        """Updates existing entries"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        # Update existing word with new definition
        entries = [
            {
                "word": "בראשית",
                "definition": "In the very beginning",
                "part_of_speech": "noun",
            }
        ]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", entries
        )

        assert result["updated"] >= 1

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_mixed(self, mock_mcp_db):
        """Handles mix of inserts and updates"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [
            {"word": "בראשית", "definition": "Updated def", "part_of_speech": "noun"},
            {"word": "חדש", "definition": "new word", "part_of_speech": "adjective"},
        ]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", entries
        )

        assert result["created"] + result["updated"] == 2

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_returns_counts(self, mock_mcp_db):
        """Returns created/updated/total counts"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "test", "definition": "test def", "part_of_speech": "noun"}]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", entries
        )

        assert "created" in result
        assert "updated" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_empty_array(self, mock_mcp_db):
        """Handles empty entries array"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        result = await upsert_dictionary_entries(mock_mcp_db, "heb", [])

        assert result["created"] == 0
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_language_not_found(self, mock_mcp_db):
        """Returns error for nonexistent language"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "test", "definition": "test", "part_of_speech": "noun"}]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "nonexistent", entries
        )

        assert "error" in result
        assert result["error"]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_upsert_dictionary_entries_validates_entries(self, mock_mcp_db):
        """Validates entry structure"""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        # Missing required field 'definition'
        entries = [{"word": "test", "part_of_speech": "noun"}]

        result = await upsert_dictionary_entries(
            mock_mcp_db, "heb", entries
        )

        assert "error" in result
        assert result["error"]["code"] == "validation_error"

    @pytest.mark.asyncio
    async def test_upsert_rejects_oversized_word(self, mock_mcp_db):
        """Words exceeding max_length are rejected, not written."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries
        entries = [{"word": "x" * 300, "definition": "test"}]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)
        assert "error" in result or result.get("failed", 0) > 0

    @pytest.mark.asyncio
    async def test_upsert_rejects_wrong_type_definition(self, mock_mcp_db):
        """Definition must be a string, not a number or dict."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries
        entries = [{"word": "test", "definition": 12345}]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)
        assert "error" in result or result.get("failed", 0) > 0

    @pytest.mark.asyncio
    async def test_upsert_rejects_dollar_prefix_keys(self, mock_mcp_db):
        """Entries with $-prefixed keys (operator injection attempt) are rejected."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries
        entries = [{"word": "test", "definition": "ok", "$set": {"x": 1}}]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)
        assert "error" in result or result.get("failed", 0) > 0

    @pytest.mark.asyncio
    async def test_upsert_still_accepts_valid_entry(self, mock_mcp_db):
        """Regression: normal LLM-shaped entries still accepted after validation."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries
        entries = [{"word": "shalom", "definition": "peace", "part_of_speech": "noun",
                    "examples": ["shalom aleichem"]}]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)
        assert result.get("created", 0) + result.get("updated", 0) >= 1

    @pytest.mark.asyncio
    async def test_upsert_sets_human_verified_on_new_dictionary_doc(self, mock_mcp_db):
        """Regression: entries in a brand-new dictionary doc (insert_one path) come
        out human_verified=True — this tool is only reachable via the chat approval
        flow, so a write reaching persistence has already been human-reviewed."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        # "english" is a valid language with no dictionary doc yet (see
        # TEST_DICTIONARIES in conftest.py), forcing the insert_one branch.
        entries = [{"word": "new", "definition": "not old", "part_of_speech": "adjective"}]
        await upsert_dictionary_entries(mock_mcp_db, "english", entries)

        coll = mock_mcp_db.get_collection("dictionaries")
        inserted_doc = coll.insert_one.call_args.args[0]
        assert inserted_doc["entries"][0]["human_verified"] is True

    @pytest.mark.asyncio
    async def test_upsert_sets_human_verified_on_pushed_entry(self, mock_mcp_db):
        """Regression: a new word pushed into an existing dictionary doc ($push path)
        comes out human_verified=True."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "newword", "definition": "brand new", "part_of_speech": "noun"}]
        await upsert_dictionary_entries(mock_mcp_db, "heb", entries)

        coll = mock_mcp_db.get_collection("dictionaries")
        pushed_entry = coll.update_one.call_args.args[1]["$push"]["entries"]
        assert pushed_entry["human_verified"] is True

    @pytest.mark.asyncio
    async def test_upsert_flips_human_verified_on_existing_unverified_entry(self, mock_mcp_db):
        """Direct regression test for the reported bug: an AI-suggested correction to
        an entry that's currently human_verified=False (see 'אלהים' in
        TEST_DICTIONARIES, conftest.py) must come out verified once a human approves
        the tool call that saves it, matching routes/dictionary.py's REST behavior."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "אלהים", "definition": "corrected: God, gods (plural form)",
                     "part_of_speech": "noun"}]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)
        assert result["updated"] == 1

        coll = mock_mcp_db.get_collection("dictionaries")
        set_payload = coll.update_one.call_args.args[1]["$set"]
        # Don't hardcode the fixture's entry index — assert on whichever key was set.
        merged_entry = next(iter(set_payload.values()))
        assert merged_entry["human_verified"] is True
        assert merged_entry["definition"] == "corrected: God, gods (plural form)"

    @pytest.mark.asyncio
    async def test_upsert_rejects_client_supplied_human_verified(self, mock_mcp_db):
        """Contract lock: human_verified is never client-settable, only server-forced.
        CreateEntryRequest has extra='forbid' and no human_verified field, so an entry
        payload trying to set it (e.g. a misbehaving LLM claiming its own entry is
        verified) is rejected outright rather than silently accepted or overridden."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [{"word": "test", "definition": "def", "human_verified": True}]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)

        assert "error" in result
        assert result["error"]["code"] == "validation_error"

    @pytest.mark.asyncio
    async def test_upsert_duplicate_word_in_batch_does_not_crash(self, mock_mcp_db):
        """Regression: a batch that repeats the same new word twice used to raise
        IndexError. The second occurrence took the update ($set) branch against an
        index that only exists after the first occurrence's $push executes, but the
        code indexed into the pre-loop entries snapshot, which doesn't have it yet.
        The second occurrence should win and merge cleanly, not crash."""
        from mcp_server.tools.dictionary import upsert_dictionary_entries

        entries = [
            {"word": "dup_test", "definition": "first def", "part_of_speech": "noun"},
            {"word": "dup_test", "definition": "corrected def", "part_of_speech": "noun"},
        ]
        result = await upsert_dictionary_entries(mock_mcp_db, "heb", entries)

        assert "error" not in result
        assert result["created"] == 1
        assert result["updated"] == 1

        coll = mock_mcp_db.get_collection("dictionaries")
        last_set = coll.update_one.call_args_list[-1].args[1]["$set"]
        merged_entry = next(iter(last_set.values()))
        assert merged_entry["definition"] == "corrected def"
        assert merged_entry["human_verified"] is True
