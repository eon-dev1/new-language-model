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
                    {"name": "phonology", "description": "", "notes": [], ...},
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
    async def test_get_categories_empty_shells_have_empty_defaults(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """Empty category shells should have empty default values."""
        response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")

        assert response.status_code == 200
        data = response.json()

        for category in data["categories"]:
            assert category["description"] == "", f"Expected empty description for {category['name']}"
            assert category["notes"] == [], f"Expected empty notes for {category['name']}"
            assert category["human_verified"] is False, f"Expected human_verified=False for {category['name']}"


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
            "notes": [{"text": "Test note for phonology", "human_verified": False}],
            "examples": [{"source_text": "Example phonology pattern", "english": "", "analysis": "", "human_verified": False}]
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
            "notes": [
                {"text": "Phonology note 1", "human_verified": False},
                {"text": "Phonology note 2", "human_verified": False}
            ],
            "examples": [
                {"source_text": "Example 1", "english": "", "analysis": "", "human_verified": False},
                {"source_text": "Example 2", "english": "", "analysis": "", "human_verified": False}
            ]
        }

        post_response = await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        assert post_response.status_code == 200, f"POST failed: {post_response.text}"

        # Verify via GET
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()

        # Find phonology category
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)
        assert phonology is not None, "Phonology category not found"

        # Category should have our content in flat fields
        assert phonology["notes"] == [
            {"text": "Phonology note 1", "human_verified": False},
            {"text": "Phonology note 2", "human_verified": False}
        ]
        assert phonology["examples"] == [
            {"source_text": "Example 1", "english": "", "analysis": "", "human_verified": False},
            {"source_text": "Example 2", "english": "", "analysis": "", "human_verified": False}
        ]

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
            ("phonology", {"notes": [{"text": "Phonology notes", "human_verified": False}], "examples": [], "subcategories": []}),
            ("morphology", {"notes": [{"text": "Morphology notes", "human_verified": False}], "examples": [], "subcategories": []}),
            ("syntax", {"notes": [{"text": "Syntax notes", "human_verified": False}], "examples": [], "subcategories": []}),
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
            assert cat["notes"] == content["notes"], f"Notes mismatch for {category_name}"


class TestSubcategoryVerification:
    """Tests for PATCH /api/grammar/{language}/categories/{category}/subcategories/{index}/verify."""

    @pytest.mark.asyncio
    async def test_verify_subcategory_success(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to verify individual subcategories.
        """
        # First create a category with subcategories
        category_data = {
            "notes": [{"text": "Test notes", "human_verified": False}],
            "subcategories": [
                {"name": "Vowel Inventory", "content": "Five vowels", "examples": ["a", "e"], "human_verified": False},
                {"name": "Consonant Inventory", "content": "Many consonants", "examples": ["b", "d"], "human_verified": False}
            ],
            "examples": []
        }

        post_response = await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )
        assert post_response.status_code == 200, f"Setup failed: {post_response.text}"

        # Verify the first subcategory
        verify_response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/subcategories/0/verify",
            json={"human_verified": True}
        )
        assert verify_response.status_code == 200, f"Verify failed: {verify_response.text}"

        verify_data = verify_response.json()
        assert verify_data["success"] is True
        assert verify_data["subcategory_index"] == 0
        assert verify_data["subcategory_name"] == "Vowel Inventory"
        assert verify_data["human_verified"] is True

        # Verify persisted in GET
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)

        assert phonology["subcategories"][0]["human_verified"] is True
        assert phonology["subcategories"][1].get("human_verified", False) is False

    @pytest.mark.asyncio
    async def test_verify_subcategory_invalid_index(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should return 400 for out-of-range subcategory index.
        """
        # Create category with 2 subcategories
        category_data = {
            "notes": [],
            "subcategories": [
                {"name": "Sub1", "content": "Content 1", "examples": [], "human_verified": False},
                {"name": "Sub2", "content": "Content 2", "examples": [], "human_verified": False}
            ],
            "examples": []
        }

        await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        # Try to verify index 5 (out of range)
        response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/subcategories/5/verify",
            json={"human_verified": True}
        )
        assert response.status_code == 400
        assert "out of range" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_verify_subcategory_toggle_off(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to un-verify a subcategory.
        """
        # Create and verify a subcategory
        category_data = {
            "notes": [],
            "subcategories": [{"name": "Test Sub", "content": "Test", "examples": [], "human_verified": False}],
            "examples": []
        }

        await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        # Verify it
        await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/subcategories/0/verify",
            json={"human_verified": True}
        )

        # Un-verify it
        response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/subcategories/0/verify",
            json={"human_verified": False}
        )
        assert response.status_code == 200
        assert response.json()["human_verified"] is False

        # Verify persisted
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)
        assert phonology["subcategories"][0]["human_verified"] is False


class TestNoteVerification:
    """Tests for PATCH /api/grammar/{language}/categories/{category}/notes/{index}/verify."""

    @pytest.mark.asyncio
    async def test_verify_note_success(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to verify individual notes.
        """
        # First create a category with notes (using new NoteData format)
        category_data = {
            "notes": [
                {"text": "First note about phonology", "human_verified": False},
                {"text": "Second note about sounds", "human_verified": False}
            ],
            "subcategories": [],
            "examples": []
        }

        post_response = await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )
        assert post_response.status_code == 200, f"Setup failed: {post_response.text}"

        # Verify the first note
        verify_response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/notes/0/verify",
            json={"human_verified": True}
        )
        assert verify_response.status_code == 200, f"Verify failed: {verify_response.text}"

        verify_data = verify_response.json()
        assert verify_data["success"] is True
        assert verify_data["note_index"] == 0
        assert verify_data["human_verified"] is True

        # Verify persisted in GET
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)

        assert phonology["notes"][0]["human_verified"] is True
        assert phonology["notes"][1].get("human_verified", False) is False

    @pytest.mark.asyncio
    async def test_verify_note_invalid_index(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should return 400 for out-of-range note index.
        """
        # Create category with 2 notes
        category_data = {
            "notes": [
                {"text": "Note 1", "human_verified": False},
                {"text": "Note 2", "human_verified": False}
            ],
            "subcategories": [],
            "examples": []
        }

        await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        # Try to verify index 5 (out of range)
        response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/notes/5/verify",
            json={"human_verified": True}
        )
        assert response.status_code == 400
        assert "out of range" in response.json()["detail"]


class TestExampleVerification:
    """Tests for PATCH /api/grammar/{language}/categories/{category}/examples/{index}/verify."""

    @pytest.mark.asyncio
    async def test_verify_example_success(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to verify individual examples.
        """
        # First create a category with examples
        category_data = {
            "notes": [],
            "subcategories": [],
            "examples": [
                {"source_text": "Example text 1", "english": "Translation 1", "analysis": "Analysis 1", "human_verified": False},
                {"source_text": "Example text 2", "english": "Translation 2", "analysis": "Analysis 2", "human_verified": False}
            ]
        }

        post_response = await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )
        assert post_response.status_code == 200, f"Setup failed: {post_response.text}"

        # Verify the first example
        verify_response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/examples/0/verify",
            json={"human_verified": True}
        )
        assert verify_response.status_code == 200, f"Verify failed: {verify_response.text}"

        verify_data = verify_response.json()
        assert verify_data["success"] is True
        assert verify_data["example_index"] == 0
        assert verify_data["human_verified"] is True

        # Verify persisted in GET
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)

        assert phonology["examples"][0]["human_verified"] is True
        assert phonology["examples"][1].get("human_verified", False) is False

    @pytest.mark.asyncio
    async def test_verify_example_invalid_index(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should return 400 for out-of-range example index.
        """
        # Create category with 2 examples
        category_data = {
            "notes": [],
            "subcategories": [],
            "examples": [
                {"source_text": "Ex 1", "english": "En 1", "analysis": "", "human_verified": False},
                {"source_text": "Ex 2", "english": "En 2", "analysis": "", "human_verified": False}
            ]
        }

        await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        # Try to verify index 5 (out of range)
        response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/examples/5/verify",
            json={"human_verified": True}
        )
        assert response.status_code == 400
        assert "out of range" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_verify_example_toggle_off(
        self,
        async_client: AsyncClient,
        clean_test_language: str
    ):
        """
        Should be able to un-verify an example.
        """
        # Create and verify an example
        category_data = {
            "notes": [],
            "subcategories": [],
            "examples": [{"source_text": "Test", "english": "Test", "analysis": "", "human_verified": False}]
        }

        await async_client.post(
            f"/api/grammar/{clean_test_language}/categories/phonology",
            json=category_data
        )

        # Verify it
        await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/examples/0/verify",
            json={"human_verified": True}
        )

        # Un-verify it
        response = await async_client.patch(
            f"/api/grammar/{clean_test_language}/categories/phonology/examples/0/verify",
            json={"human_verified": False}
        )
        assert response.status_code == 200
        assert response.json()["human_verified"] is False

        # Verify persisted
        get_response = await async_client.get(f"/api/grammar/{clean_test_language}/categories")
        data = get_response.json()
        phonology = next((c for c in data["categories"] if c["name"] == "phonology"), None)
        assert phonology["examples"][0]["human_verified"] is False
