# tests/unit/routes/test_dictionary_empty_state.py
"""
Tests for dictionary empty state handling.

Verifies that:
1. GET returns empty list (not 404) when no dictionary exists
2. POST creates dictionary document if missing (upsert pattern)
3. Creating first entry from empty state succeeds end-to-end

These tests use the real MongoDB connection via fixtures.
"""

import pytest
from httpx import AsyncClient


class TestDictionaryEmptyStateGET:
    """Tests for GET /api/dictionary/{language}/entries with empty state."""

    @pytest.mark.asyncio
    async def test_get_entries_returns_empty_list_when_no_documents(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        GET should return empty list, not 404, when no dictionary exists.

        Expected response:
            {
                "language_code": "<test_language>",
                "entries": [],
                "count": 0
            }
        """
        response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")

        # Should NOT return 404
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["language_code"] == clean_test_language
        assert data["entries"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_entries_returns_200_not_404(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """Verify we get 200 status, not 404, for non-existent dictionary."""
        response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")

        # This is the critical assertion - current code returns 404
        assert response.status_code != 404, "GET should not return 404 for empty dictionary"
        assert response.status_code == 200


class TestDictionaryEmptyStatePOST:
    """Tests for POST /api/dictionary/{language}/entries with empty state."""

    @pytest.mark.asyncio
    async def test_post_entry_creates_dictionary_document_if_missing(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        POST should create dictionary document when none exists (upsert pattern).

        Even if no dictionary document exists for the language, creating an entry
        should succeed by first creating the dictionary document.
        """
        entry_data = {
            "word": "testword",
            "definition": "A word used for testing purposes",
            "part_of_speech": "noun",
            "examples": ["This is a testword example."]
        }

        response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries",
            json=entry_data
        )

        # Should NOT return 404
        assert response.status_code != 404, f"POST should not return 404: {response.text}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert data["word"] == "testword"
        assert data["action"] == "created"

    @pytest.mark.asyncio
    async def test_post_entry_first_entry_succeeds(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Creating first entry in empty dictionary should succeed end-to-end.

        After POST, GET should return the entry.
        """
        # Create first entry
        entry_data = {
            "word": "firstword",
            "definition": "The very first word in the dictionary",
            "part_of_speech": "noun",
            "examples": []
        }

        post_response = await async_client.post(
            f"/api/dictionary/{clean_test_language}/entries",
            json=entry_data
        )

        assert post_response.status_code == 200, f"POST failed: {post_response.text}"

        # Verify it shows up in GET
        get_response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")

        assert get_response.status_code == 200
        data = get_response.json()

        assert data["count"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["word"] == "firstword"

    @pytest.mark.asyncio
    async def test_post_multiple_entries_from_empty_state(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to add multiple entries starting from empty state.
        """
        words = [
            {"word": "alpha", "definition": "First letter", "examples": []},
            {"word": "beta", "definition": "Second letter", "examples": []},
            {"word": "gamma", "definition": "Third letter", "examples": []},
        ]

        for entry in words:
            response = await async_client.post(
                f"/api/dictionary/{clean_test_language}/entries",
                json=entry
            )
            assert response.status_code == 200, f"Failed to add {entry['word']}: {response.text}"

        # Verify all entries exist
        get_response = await async_client.get(f"/api/dictionary/{clean_test_language}/entries")
        data = get_response.json()

        assert data["count"] == 3
        entry_words = [e["word"] for e in data["entries"]]
        assert "alpha" in entry_words
        assert "beta" in entry_words
        assert "gamma" in entry_words
