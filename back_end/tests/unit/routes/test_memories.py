# tests/unit/routes/test_memories.py
"""
Tests for GET/POST/PUT/DELETE /api/memories/{language}/notes.

Verifies:
- GET returns empty array (not 404) when no notes document exists
- POST creates a note; it appears in GET with the correct id
- Created notes have no human_verified field
- PUT updates text and updated_at; PUT with unknown id → 404
- DELETE removes the note; DELETE with unknown id → 404
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator
import uuid

from constants import Collection


# === Cleanup fixture ===

@pytest_asyncio.fixture
async def clean_notes_language(connected_db) -> AsyncGenerator[str, None]:
    """Provide a unique test language code and clean up language_notes after the test."""
    lang = f"test_mem_{uuid.uuid4().hex[:8]}"
    yield lang
    db = connected_db.get_database()
    await db[Collection.LANGUAGE_NOTES].delete_many({"language_code": lang})


# === Helper ===

async def _create_note(client: AsyncClient, lang: str, text: str) -> str:
    """POST a note and return the note_id."""
    resp = await client.post(f"/api/memories/{lang}/notes", json={"text": text})
    assert resp.status_code == 200, f"Setup POST failed: {resp.text}"
    return resp.json()["note_id"]


# === Tests ===

class TestNotesEmptyState:
    """GET /api/memories/{language}/notes with no notes document."""

    @pytest.mark.asyncio
    async def test_get_notes_empty_language_returns_200(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Language with no notes document should return 200 with empty array, not 404."""
        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert data["language_code"] == clean_notes_language
        assert data["notes"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_notes_not_404_for_new_language(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Explicitly confirm the response is not 404."""
        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        assert resp.status_code != 404, "GET should never return 404 for missing notes"


class TestNotesCreate:
    """POST /api/memories/{language}/notes."""

    @pytest.mark.asyncio
    async def test_post_note_returns_success(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST should return success=True and a note_id."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"text": "A useful language note"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["note_id"], str) and len(data["note_id"]) > 0
        assert data["language_code"] == clean_notes_language

    @pytest.mark.asyncio
    async def test_post_note_appears_in_get(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Created note should appear in GET response."""
        note_id = await _create_note(async_client, clean_notes_language, "Vowels are long in open syllables")

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["notes"]) == 1
        assert data["notes"][0]["id"] == note_id
        assert data["notes"][0]["text"] == "Vowels are long in open syllables"

    @pytest.mark.asyncio
    async def test_post_note_has_no_human_verified_field(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Notes must NOT contain a human_verified field — presence implies trust."""
        await _create_note(async_client, clean_notes_language, "Test note")

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = resp.json()["notes"][0]
        assert "human_verified" not in note, "Notes must not have human_verified field"

    @pytest.mark.asyncio
    async def test_post_note_has_timestamps(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Created note should have created_at and updated_at timestamps."""
        await _create_note(async_client, clean_notes_language, "Timestamped note")

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = resp.json()["notes"][0]
        assert "created_at" in note
        assert "updated_at" in note

    @pytest.mark.asyncio
    async def test_post_multiple_notes(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Multiple POST calls should accumulate notes."""
        await _create_note(async_client, clean_notes_language, "Note one")
        await _create_note(async_client, clean_notes_language, "Note two")
        await _create_note(async_client, clean_notes_language, "Note three")

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        data = resp.json()
        assert data["count"] == 3
        texts = [n["text"] for n in data["notes"]]
        assert "Note one" in texts
        assert "Note two" in texts
        assert "Note three" in texts


class TestNotesUpdate:
    """PUT /api/memories/{language}/notes/{note_id}."""

    @pytest.mark.asyncio
    async def test_put_note_updates_text(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT should update the note text."""
        note_id = await _create_note(async_client, clean_notes_language, "Original text")

        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"text": "Updated text"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        get = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = next(n for n in get.json()["notes"] if n["id"] == note_id)
        assert note["text"] == "Updated text"

    @pytest.mark.asyncio
    async def test_put_note_updates_updated_at(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT should change updated_at timestamp."""
        note_id = await _create_note(async_client, clean_notes_language, "Before update")

        get_before = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        updated_at_before = next(n for n in get_before.json()["notes"] if n["id"] == note_id)["updated_at"]

        # Small delay so timestamps differ
        import asyncio
        await asyncio.sleep(0.01)

        await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"text": "After update"}
        )

        get_after = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        updated_at_after = next(n for n in get_after.json()["notes"] if n["id"] == note_id)["updated_at"]

        assert updated_at_after >= updated_at_before

    @pytest.mark.asyncio
    async def test_put_nonexistent_note_returns_404(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT with unknown note_id should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{fake_id}",
            json={"text": "Should not work"}
        )
        assert resp.status_code == 404


class TestNotesDelete:
    """DELETE /api/memories/{language}/notes/{note_id}."""

    @pytest.mark.asyncio
    async def test_delete_note_removes_it(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """DELETE should remove the note from GET results."""
        note_id = await _create_note(async_client, clean_notes_language, "To be deleted")

        resp = await async_client.delete(
            f"/api/memories/{clean_notes_language}/notes/{note_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        get = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        ids = [n["id"] for n in get.json()["notes"]]
        assert note_id not in ids

    @pytest.mark.asyncio
    async def test_delete_reduces_count(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Count should decrease by 1 after delete."""
        await _create_note(async_client, clean_notes_language, "Keep this")
        note_id = await _create_note(async_client, clean_notes_language, "Delete this")

        await async_client.delete(f"/api/memories/{clean_notes_language}/notes/{note_id}")

        get = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        data = get.json()
        assert data["count"] == 1
        assert data["notes"][0]["text"] == "Keep this"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_note_returns_404(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """DELETE with unknown note_id should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await async_client.delete(
            f"/api/memories/{clean_notes_language}/notes/{fake_id}"
        )
        assert resp.status_code == 404


class TestNotesValidation:
    """POST/PUT validation — invalid inputs return correct error codes."""

    @pytest.mark.asyncio
    async def test_post_empty_text_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with empty text violates min_length=1 → 422."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"text": ""}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_missing_text_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST without text field → 422 (required field)."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_whitespace_only_text_accepted(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with whitespace-only text should be accepted; stored text must not be stripped."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"text": "   "}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        note_id = resp.json()["note_id"]

        # Verify stored text is exactly "   " (not stripped)
        get = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = next(n for n in get.json()["notes"] if n["id"] == note_id)
        assert note["text"] == "   ", f"Expected text to be exactly '   ', got {repr(note['text'])}"

    @pytest.mark.asyncio
    async def test_put_empty_text_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT with empty text violates min_length=1 → 422."""
        note_id = await _create_note(async_client, clean_notes_language, "Original text")

        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"text": ""}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
