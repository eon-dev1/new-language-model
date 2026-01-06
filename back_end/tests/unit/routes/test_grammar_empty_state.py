# tests/unit/routes/test_grammar_empty_state.py
"""
Tests for grammar empty state handling.

Verifies that:
1. GET returns 5 empty category shells (not 404) when no grammar exists
2. POST creates grammar document if missing (upsert pattern)
3. Updating categories from empty state succeeds end-to-end

These tests use the real MongoDB connection via fixtures.
"""

import pytest
from httpx import AsyncClient


# Valid grammar categories (must match routes/grammar.py VALID_CATEGORIES)
VALID_CATEGORIES = ["phonology", "morphology", "syntax", "semantics", "discourse"]


class TestGrammarEmptyStateGET:
    """Tests for GET /api/grammar/{language}/categories with empty state."""

    @pytest.mark.asyncio
    async def test_get_categories_returns_shells_when_no_documents(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        GET should return 5 empty category shells, not 404, when no grammar exists.

        Expected response:
            {
                "language_code": "<test_language>",
                "categories": [
                    {"name": "phonology", "human": null, "ai": null},
                    {"name": "morphology", "human": null, "ai": null},
                    ...
                ],
                "count": 5
            }
        """
        response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")

        # Should NOT return 404
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["language_code"] == clean_test_language
        assert data["count"] == 5
        assert len(data["categories"]) == 5

        # Verify all 5 categories are present
        category_names = [c["name"] for c in data["categories"]]
        for expected_cat in VALID_CATEGORIES:
            assert expected_cat in category_names, f"Missing category: {expected_cat}"

    @pytest.mark.asyncio
    async def test_get_categories_returns_200_not_404(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """Verify we get 200 status, not 404, for non-existent grammar."""
        response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")

        # This is the critical assertion - current code returns 404
        assert response.status_code != 404, "GET should not return 404 for empty grammar"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_categories_empty_shells_have_null_versions(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """Empty category shells should have null human and ai versions."""
        response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")

        assert response.status_code == 200
        data = response.json()

        for category in data["categories"]:
            assert category["human"] is None, f"Expected null human for {category['name']}"
            assert category["ai"] is None, f"Expected null ai for {category['name']}"


class TestGrammarEmptyStatePOST:
    """Tests for POST /api/grammar/{language}/categories/{name} with empty state."""

    @pytest.mark.asyncio
    async def test_post_category_creates_grammar_document_if_missing(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        POST should create grammar document when none exists (upsert pattern).

        Even if no grammar document exists for the language, updating a category
        should succeed by first creating the grammar document.
        """
        category_data = {
            "notes": ["Test note for phonology"],
            "examples": ["Example phonology pattern"]
        }

        response = await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        # Should NOT return 404
        assert response.status_code != 404, f"POST should not return 404: {response.text}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert data["category_name"] == "phonology"

    @pytest.mark.asyncio
    async def test_post_category_content_persists(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Content saved via POST should be retrievable via GET.
        """
        # Save content
        category_data = {
            "notes": ["Phonology note 1", "Phonology note 2"],
            "examples": ["Example 1", "Example 2"]
        }

        post_response = await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        assert post_response.status_code == 200, f"POST failed: {post_response.text}"

        # Verify via GET
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")

        assert get_response.status_code == 200
        data = get_response.json()

        # Find phonology category
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)
        assert phonology is not None, "Phonology category not found"

        # Human version should have our content
        assert phonology["human"] is not None, "Human version should exist after POST"
        assert phonology["human"]["notes"] == ["Phonology note 1", "Phonology note 2"]
        assert phonology["human"]["examples"] == ["Example 1", "Example 2"]

    @pytest.mark.asyncio
    async def test_post_multiple_categories_from_empty_state(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to update multiple categories starting from empty state.
        """
        updates = [
            ("phonology", {"notes": ["Phonology notes"], "examples": []}),
            ("morphology", {"notes": ["Morphology notes"], "examples": []}),
            ("syntax", {"notes": ["Syntax notes"], "examples": []}),
        ]

        for category_name, content in updates:
            response = await async_client.post(
                f"/api/grammar/{clean_test_language}/categories/{category_name}",
                json=content
            )
            assert response.status_code == 200, f"Failed to update {category_name}: {response.text}"

        # Verify all updates persisted
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()

        for category_name, content in updates:
            cat = next((c for c in data["categories"] if c["name"] == category_name), None)
            assert cat is not None, f"Category {category_name} not found"
            assert cat["human"] is not None, f"Human version missing for {category_name}"
            assert cat["human"]["notes"] == content["notes"]
