# tests/unit/routes/test_dictionary_delete.py
"""
Tests for dictionary entry deletion (POST /api/dictionary/{language}/entries/delete).

These are the tests that distinguish the shipped design from the rejected,
simpler alternatives (case-sensitive $pull, $inc-based entry_count, no
$type guard) — see __plans__/dictionary-delete.md §3.3 and §8.1.

Uses the real MongoDB connection via fixtures, same pattern as
test_dictionary_empty_state.py.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from constants import Collection
from db_connector.connection import MongoDBConnector


async def _create_entry(async_client: AsyncClient, language: str, word: str) -> None:
    response = await async_client.post(
        f"/api/dictionary/{language}/entries",
        json={"word": word, "definition": f"definition of {word}", "examples": []},
    )
    assert response.status_code == 200, f"Failed to seed '{word}': {response.text}"


async def _insert_raw_entry(
    connected_db: MongoDBConnector, language: str, entries: list[dict]
) -> None:
    """Insert a dictionary document directly, bypassing app-level normalization —
    used to simulate MCP-authored (unnormalized) or malformed legacy data."""
    now = datetime.now(timezone.utc)
    database = connected_db.get_database()
    await database[Collection.DICTIONARIES].insert_one(
        {
            "language_code": language,
            "dictionary_name": f"{language} dictionary",
            "entries": entries,
            "entry_count": len(entries),
            "created_at": now,
        }
    )


class TestDictionaryDeleteBasic:
    @pytest.mark.asyncio
    async def test_single_delete(self, async_client, clean_test_language):
        await _create_entry(async_client, clean_test_language, "alpha")

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha"]},
        )
        assert response.status_code == 200
        assert response.json()["absent"] == ["alpha"]

        get_response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")
        assert get_response.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_bulk_delete(self, async_client, clean_test_language):
        for word in ["alpha", "beta", "gamma"]:
            await _create_entry(async_client, clean_test_language, word)

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha", "beta"]},
        )
        assert response.status_code == 200
        assert set(response.json()["absent"]) == {"alpha", "beta"}

        get_response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")
        remaining = [e["word"] for e in get_response.json()["entries"]]
        assert remaining == ["gamma"]

    @pytest.mark.asyncio
    async def test_partial_not_found_checks_ground_truth(self, async_client, clean_test_language, connected_db):
        await _create_entry(async_client, clean_test_language, "alpha")

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha", "nonexistent"]},
        )
        assert response.status_code == 200
        # Response no longer distinguishes found vs not-found — both are "absent".
        assert set(response.json()["absent"]) == {"alpha", "nonexistent"}

        # Ground truth: only the real word was actually removed.
        database = connected_db.get_database()
        doc = await database[Collection.DICTIONARIES].find_one({"language_code": clean_test_language})
        assert [e["word"] for e in doc["entries"]] == []

    @pytest.mark.asyncio
    async def test_all_not_found_returns_200_not_500(self, async_client, clean_test_language):
        await _create_entry(async_client, clean_test_language, "alpha")

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["nonexistent1", "nonexistent2"]},
        )
        assert response.status_code == 200
        assert set(response.json()["absent"]) == {"nonexistent1", "nonexistent2"}

        get_response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")
        assert get_response.json()["count"] == 1

    @pytest.mark.asyncio
    async def test_404_for_missing_language(self, async_client, clean_test_language):
        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha"]},
        )
        assert response.status_code == 404


class TestDictionaryDeleteEntryCount:
    @pytest.mark.asyncio
    async def test_entry_count_matches_len_entries_after_delete(self, async_client, clean_test_language, connected_db):
        for word in ["alpha", "beta", "gamma"]:
            await _create_entry(async_client, clean_test_language, word)

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha"]},
        )
        assert response.status_code == 200

        database = connected_db.get_database()
        doc = await database[Collection.DICTIONARIES].find_one({"language_code": clean_test_language})
        assert doc["entry_count"] == len(doc["entries"]) == 2

    @pytest.mark.asyncio
    async def test_entry_count_correct_under_concurrent_duplicate_requests(self, async_client, clean_test_language, connected_db):
        await _create_entry(async_client, clean_test_language, "alpha")

        results = await asyncio.gather(
            async_client.post(
                f"/api/dictionary/{clean_test_language}/entries/delete", json={"words": ["alpha"]}
            ),
            async_client.post(
                f"/api/dictionary/{clean_test_language}/entries/delete", json={"words": ["alpha"]}
            ),
        )
        for response in results:
            assert response.status_code == 200

        database = connected_db.get_database()
        doc = await database[Collection.DICTIONARIES].find_one({"language_code": clean_test_language})
        assert doc["entry_count"] == len(doc["entries"]) == 0


class TestDictionaryDeleteNormalization:
    @pytest.mark.asyncio
    async def test_case_insensitive_delete_of_mcp_style_word(self, async_client, clean_test_language, connected_db):
        # MCP write path never lowercases `word` — simulate that directly.
        await _insert_raw_entry(
            connected_db,
            clean_test_language,
            [{"word": "Alpha", "definition": "first letter", "examples": [], "human_verified": False}],
        )

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha"]},
        )
        assert response.status_code == 200

        database = connected_db.get_database()
        doc = await database[Collection.DICTIONARIES].find_one({"language_code": clean_test_language})
        assert doc["entries"] == []

    @pytest.mark.asyncio
    async def test_whitespace_insensitive_delete_of_padded_word(self, async_client, clean_test_language, connected_db):
        await _insert_raw_entry(
            connected_db,
            clean_test_language,
            [{"word": "  alpha  ", "definition": "first letter", "examples": [], "human_verified": False}],
        )

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["alpha"]},
        )
        assert response.status_code == 200

        database = connected_db.get_database()
        doc = await database[Collection.DICTIONARIES].find_one({"language_code": clean_test_language})
        assert doc["entries"] == []

    @pytest.mark.asyncio
    async def test_malformed_non_string_word_does_not_break_request(self, async_client, clean_test_language, connected_db):
        await _insert_raw_entry(
            connected_db,
            clean_test_language,
            [
                {"word": 12345, "definition": "malformed legacy entry", "examples": [], "human_verified": False},
                {"word": "beta", "definition": "second letter", "examples": [], "human_verified": False},
            ],
        )

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries/delete",
            json={"words": ["beta"]},
        )
        assert response.status_code == 200
        assert response.json()["absent"] == ["beta"]

        database = connected_db.get_database()
        doc = await database[Collection.DICTIONARIES].find_one({"language_code": clean_test_language})
        # The malformed entry is left untouched; only 'beta' was removed.
        assert [e["word"] for e in doc["entries"]] == [12345]


class TestDictionaryDeleteWordIndexSync:
    @pytest.mark.asyncio
    async def test_in_dictionary_flag_flipped_false_after_delete(self, async_client, clean_test_language, connected_db):
        await _create_entry(async_client, clean_test_language, "alpha")

        database = connected_db.get_database()
        now = datetime.now(timezone.utc)
        try:
            await database[Collection.WORD_INDEX].insert_one(
                {
                    "language_code": clean_test_language,
                    "word": "alpha",
                    "total_count": 1,
                    "book_count": 1,
                    "chapter_count": 1,
                    "occurrences": [],
                    "first_seen": {"book_code": "GEN", "chapter": 1, "verse": 1},
                    "in_dictionary": True,
                    "last_rebuilt": now,
                }
            )

            response = await async_client.post(
                f"/api/dictionary/{clean_test_language}/entries/delete",
                json={"words": ["alpha"]},
            )
            assert response.status_code == 200

            wi_doc = await database[Collection.WORD_INDEX].find_one(
                {"language_code": clean_test_language, "word": "alpha"}
            )
            assert wi_doc["in_dictionary"] is False
        finally:
            # clean_test_language doesn't clean word_index — clean up explicitly.
            await database[Collection.WORD_INDEX].delete_many({"language_code": clean_test_language})
