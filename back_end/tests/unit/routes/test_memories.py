# tests/unit/routes/test_memories.py
"""
Tests for GET/POST/PUT/DELETE /api/memories/{language}/notes.

Verifies:
- GET returns empty array (not 404) when no notes document exists
- POST creates a note; it appears in GET with the correct id
- Created notes have no human_verified field
- PUT updates title/text and updated_at; PUT with unknown id → 404
- DELETE removes the note; DELETE with unknown id → 404
- Title/text validators strip whitespace and reject empty-after-strip
- GET against a manually-seeded title-less note returns 500 (loud-failure)
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator
from datetime import datetime, timezone
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

async def _create_note(
    client: AsyncClient, lang: str, title: str, text: str
) -> str:
    """POST a note and return the note_id."""
    resp = await client.post(
        f"/api/memories/{lang}/notes", json={"title": title, "text": text}
    )
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


class TestNotesCreate:
    """POST /api/memories/{language}/notes."""

    @pytest.mark.asyncio
    async def test_post_note_returns_success(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST should return success=True and a note_id."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "Vowel rule", "text": "A useful language note"}
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
        note_id = await _create_note(
            async_client, clean_notes_language,
            "Vowel length", "Vowels are long in open syllables",
        )

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["notes"]) == 1
        assert data["notes"][0]["id"] == note_id
        assert data["notes"][0]["title"] == "Vowel length"
        assert data["notes"][0]["text"] == "Vowels are long in open syllables"

    @pytest.mark.asyncio
    async def test_post_note_has_no_human_verified_field(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Notes must NOT contain a human_verified field — presence implies trust."""
        await _create_note(async_client, clean_notes_language, "Title", "Test note")

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = resp.json()["notes"][0]
        assert "human_verified" not in note, "Notes must not have human_verified field"

    @pytest.mark.asyncio
    async def test_post_note_has_timestamps(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Created note should have created_at and updated_at timestamps."""
        await _create_note(
            async_client, clean_notes_language, "T", "Timestamped note"
        )

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = resp.json()["notes"][0]
        assert "created_at" in note
        assert "updated_at" in note

    @pytest.mark.asyncio
    async def test_post_multiple_notes(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """Multiple POST calls should accumulate notes."""
        await _create_note(async_client, clean_notes_language, "T1", "Note one")
        await _create_note(async_client, clean_notes_language, "T2", "Note two")
        await _create_note(async_client, clean_notes_language, "T3", "Note three")

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
    async def test_put_note_updates_title_and_text(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT should update both title and text."""
        note_id = await _create_note(
            async_client, clean_notes_language, "Old title", "Original text"
        )

        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"title": "New title", "text": "Updated text"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        get = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = next(n for n in get.json()["notes"] if n["id"] == note_id)
        assert note["title"] == "New title"
        assert note["text"] == "Updated text"

    @pytest.mark.asyncio
    async def test_put_note_updates_updated_at(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT should change updated_at timestamp."""
        note_id = await _create_note(
            async_client, clean_notes_language, "T", "Before update"
        )

        get_before = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        updated_at_before = next(n for n in get_before.json()["notes"] if n["id"] == note_id)["updated_at"]

        import asyncio
        await asyncio.sleep(0.01)

        await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"title": "T", "text": "After update"}
        )

        get_after = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        updated_at_after = next(n for n in get_after.json()["notes"] if n["id"] == note_id)["updated_at"]

        assert updated_at_after > updated_at_before

    @pytest.mark.asyncio
    async def test_put_nonexistent_note_returns_404(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT with unknown note_id should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{fake_id}",
            json={"title": "T", "text": "Should not work"}
        )
        assert resp.status_code == 404


class TestNotesDelete:
    """DELETE /api/memories/{language}/notes/{note_id}."""

    @pytest.mark.asyncio
    async def test_delete_note_removes_it(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """DELETE should remove the note from GET results."""
        note_id = await _create_note(
            async_client, clean_notes_language, "T", "To be deleted"
        )

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
        await _create_note(async_client, clean_notes_language, "Keep", "Keep this")
        note_id = await _create_note(
            async_client, clean_notes_language, "Del", "Delete this"
        )

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
        """POST with empty text → 422."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "T", "text": ""}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_empty_title_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with empty title → 422."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "", "text": "Body"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_missing_text_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST without text field → 422."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "T"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_missing_title_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST without title field → 422."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"text": "Body"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_whitespace_only_text_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with whitespace-only text → 422 (validator strips first then checks)."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "T", "text": "   "}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_whitespace_only_title_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with whitespace-only title → 422 (validator strips first then checks)."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "   ", "text": "Body"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_post_strips_surrounding_whitespace(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with surrounding whitespace → 200, stored values are stripped."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "  Padded title  ", "text": "  Padded body  "}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        note_id = resp.json()["note_id"]

        get = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        note = next(n for n in get.json()["notes"] if n["id"] == note_id)
        assert note["title"] == "Padded title"
        assert note["text"] == "Padded body"

    @pytest.mark.asyncio
    async def test_post_title_too_long_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """POST with title > 200 chars → 422."""
        resp = await async_client.post(
            f"/api/memories/{clean_notes_language}/notes",
            json={"title": "x" * 201, "text": "Body"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_put_empty_text_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT with empty text → 422."""
        note_id = await _create_note(
            async_client, clean_notes_language, "T", "Original text"
        )

        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"title": "T", "text": ""}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_put_whitespace_only_title_returns_422(
        self, async_client: AsyncClient, clean_notes_language: str
    ):
        """PUT with whitespace-only title → 422."""
        note_id = await _create_note(
            async_client, clean_notes_language, "T", "Body"
        )

        resp = await async_client.put(
            f"/api/memories/{clean_notes_language}/notes/{note_id}",
            json={"title": "   ", "text": "Body"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


class TestNotesReadLoudFailure:
    """A title-less note in storage must surface as 500 on read (I6/P10)."""

    @pytest.mark.asyncio
    async def test_get_titleless_note_returns_500(
        self, async_client: AsyncClient, connected_db, clean_notes_language: str
    ):
        """Manually seed a note missing `title`; GET must return 500 (Pydantic ValidationError)."""
        db = connected_db.get_database()
        collection = db[Collection.LANGUAGE_NOTES]
        now = datetime.now(timezone.utc)
        await collection.insert_one({
            "language_code": clean_notes_language,
            "notes": [
                {
                    "id": str(uuid.uuid4()),
                    # NB: no title field — simulates a pre-migration legacy doc
                    "text": "Legacy note without title",
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "updated_at": now,
        })

        resp = await async_client.get(f"/api/memories/{clean_notes_language}/notes")
        assert resp.status_code == 500, (
            f"Expected 500 (loud-failure on missing title); got {resp.status_code}: {resp.text}"
        )
