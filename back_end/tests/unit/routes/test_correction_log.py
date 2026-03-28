# tests/unit/routes/test_correction_log.py
"""
Tests for POST/GET/PUT /api/correction-log/{language}.

Verifies:
- POST appends an entry for each content_type and returns 201
- POST with invalid content_type → 400
- POST with missing required fields → 422
- GET returns empty list (not 404) when no entries exist
- GET filter by content_type returns only matching entries
- GET pagination returns correct slice
- GET with invalid filter content_type → 400
- PUT updates what_was_wrong; all other fields unchanged
- PUT with extra body fields — only what_was_wrong changes
- PUT with unknown log_id → 404
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator
import uuid

from constants import Collection


# === Cleanup fixture ===

@pytest_asyncio.fixture
async def clean_log_language(connected_db) -> AsyncGenerator[str, None]:
    """Provide a unique test language code and clean up correction_log after the test."""
    lang = f"test_log_{uuid.uuid4().hex[:8]}"
    yield lang
    db = connected_db.get_database()
    await db[Collection.CORRECTION_LOG].delete_many({"language_code": lang})


# === Payloads for each content_type ===

BIBLE_ENTRY = {
    "content_type": "bible_verse",
    "content_reference": {"book_code": "genesis", "chapter": 1, "verse": 1},
    "original_text": "In the start God made everything",
    "what_was_wrong": "Too colloquial",
    "correction": "In the beginning God created the heavens and the earth",
}

DICTIONARY_ENTRY = {
    "content_type": "dictionary_entry",
    "content_reference": {"word": "light"},
    "original_text": "A visible form of energy",
    "what_was_wrong": "Too technical for target audience",
    "correction": "Brightness that lets us see",
}

GRAMMAR_ENTRY = {
    "content_type": "grammar_category",
    "content_reference": {"category": "phonology"},
    "original_text": "The language has 5 vowels",
    "what_was_wrong": "Missing tone description",
    "correction": "The language has 5 tonal vowels",
}


# === Helper ===

async def _append(client: AsyncClient, lang: str, payload: dict) -> str:
    """POST a correction log entry and return its log_id."""
    resp = await client.post(f"/api/correction-log/{lang}", json=payload)
    assert resp.status_code == 201, f"Setup POST failed: {resp.text}"
    return resp.json()["log_id"]


# === Tests ===

class TestCorrectionLogAppend:
    """POST /api/correction-log/{language} — happy path."""

    @pytest.mark.asyncio
    async def test_append_bible_verse_entry(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=BIBLE_ENTRY
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["log_id"], str) and len(data["log_id"]) > 0
        assert data["language_code"] == clean_log_language

    @pytest.mark.asyncio
    async def test_append_dictionary_entry(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=DICTIONARY_ENTRY
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_append_grammar_category_entry(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=GRAMMAR_ENTRY
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_appended_entry_visible_in_get(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Entry inserted via POST should appear in GET."""
        log_id = await _append(async_client, clean_log_language, BIBLE_ENTRY)

        resp = await async_client.get(f"/api/correction-log/{clean_log_language}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        entry = data["entries"][0]
        assert entry["id"] == log_id
        assert entry["content_type"] == "bible_verse"
        assert entry["original_text"] == BIBLE_ENTRY["original_text"]
        assert entry["correction"] == BIBLE_ENTRY["correction"]


class TestCorrectionLogValidation:
    """POST validation — invalid inputs return correct error codes."""

    @pytest.mark.asyncio
    async def test_invalid_content_type_returns_400(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """content_type not in the allowed set → 400 from handler (not Pydantic)."""
        payload = {**BIBLE_ENTRY, "content_type": "invalid_type"}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 400
        assert "invalid_type" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_missing_what_was_wrong_returns_422(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Omitting required field what_was_wrong → 422 Pydantic validation error."""
        payload = {k: v for k, v in BIBLE_ENTRY.items() if k != "what_was_wrong"}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_what_was_wrong_returns_422(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Empty string for what_was_wrong violates min_length=1 → 422."""
        payload = {**BIBLE_ENTRY, "what_was_wrong": ""}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_original_text_returns_422(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Omitting required field original_text → 422."""
        payload = {k: v for k, v in BIBLE_ENTRY.items() if k != "original_text"}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_correction_returns_422(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Omitting required field correction → 422."""
        payload = {k: v for k, v in BIBLE_ENTRY.items() if k != "correction"}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_empty_correction_returns_422(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Empty string for correction violates min_length=1 → 422."""
        payload = {**BIBLE_ENTRY, "correction": ""}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_missing_content_reference_returns_422(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Omitting required field content_reference → 422."""
        payload = {k: v for k, v in BIBLE_ENTRY.items() if k != "content_reference"}
        resp = await async_client.post(
            f"/api/correction-log/{clean_log_language}", json=payload
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


class TestCorrectionLogGet:
    """GET /api/correction-log/{language}."""

    @pytest.mark.asyncio
    async def test_get_empty_language_returns_200(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Language with no entries returns 200 with empty list, not 404."""
        resp = await async_client.get(f"/api/correction-log/{clean_log_language}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["language_code"] == clean_log_language
        assert data["entries"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_content_type_bible(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Filter by content_type returns only matching entries."""
        await _append(async_client, clean_log_language, BIBLE_ENTRY)
        await _append(async_client, clean_log_language, DICTIONARY_ENTRY)
        await _append(async_client, clean_log_language, GRAMMAR_ENTRY)

        resp = await async_client.get(
            f"/api/correction-log/{clean_log_language}",
            params={"content_type": "bible_verse"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert all(e["content_type"] == "bible_verse" for e in data["entries"])

    @pytest.mark.asyncio
    async def test_filter_by_content_type_dictionary(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        await _append(async_client, clean_log_language, BIBLE_ENTRY)
        await _append(async_client, clean_log_language, DICTIONARY_ENTRY)

        resp = await async_client.get(
            f"/api/correction-log/{clean_log_language}",
            params={"content_type": "dictionary_entry"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["entries"][0]["content_type"] == "dictionary_entry"

    @pytest.mark.asyncio
    async def test_filter_by_content_type_grammar(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        await _append(async_client, clean_log_language, GRAMMAR_ENTRY)
        await _append(async_client, clean_log_language, BIBLE_ENTRY)

        resp = await async_client.get(
            f"/api/correction-log/{clean_log_language}",
            params={"content_type": "grammar_category"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["entries"][0]["content_type"] == "grammar_category"

    @pytest.mark.asyncio
    async def test_pagination_page_2(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Page 2 with page_size=2 returns the third entry."""
        for i in range(3):
            payload = {**BIBLE_ENTRY, "original_text": f"Original {i}", "correction": f"Corrected {i}"}
            await _append(async_client, clean_log_language, payload)

        resp = await async_client.get(
            f"/api/correction-log/{clean_log_language}",
            params={"page": 2, "page_size": 2}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert len(data["entries"]) == 1  # 3 total, 2 per page → page 2 has 1

    @pytest.mark.asyncio
    async def test_invalid_filter_content_type_returns_400(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """GET with invalid content_type filter → 400."""
        resp = await async_client.get(
            f"/api/correction-log/{clean_log_language}",
            params={"content_type": "not_a_real_type"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_entries_returned_newest_first(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """GET should return entries sorted by created_at DESC, with _id tiebreaker."""
        # POST 3 entries with distinct original_text
        for i in range(3):
            payload = {**BIBLE_ENTRY, "original_text": f"Original {i}"}
            await _append(async_client, clean_log_language, payload)

        resp = await async_client.get(f"/api/correction-log/{clean_log_language}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        entries = data["entries"]
        assert len(entries) == 3, f"Expected 3 entries, got {len(entries)}"
        # Newest (last appended) should be first
        assert entries[0]["original_text"] == "Original 2", f"Expected 'Original 2', got {repr(entries[0]['original_text'])}"


class TestCorrectionLogUpdate:
    """PUT /api/correction-log/{language}/{log_id}."""

    @pytest.mark.asyncio
    async def test_put_updates_what_was_wrong(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """PUT should update what_was_wrong and return success."""
        log_id = await _append(async_client, clean_log_language, BIBLE_ENTRY)

        resp = await async_client.put(
            f"/api/correction-log/{clean_log_language}/{log_id}",
            json={"what_was_wrong": "Updated explanation"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["log_id"] == log_id

        # Verify via GET
        get = await async_client.get(f"/api/correction-log/{clean_log_language}")
        entry = next(e for e in get.json()["entries"] if e["id"] == log_id)
        assert entry["what_was_wrong"] == "Updated explanation"

    @pytest.mark.asyncio
    async def test_put_does_not_change_other_fields(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """PUT must not mutate original_text, correction, content_type, or content_reference."""
        log_id = await _append(async_client, clean_log_language, BIBLE_ENTRY)

        await async_client.put(
            f"/api/correction-log/{clean_log_language}/{log_id}",
            json={"what_was_wrong": "New explanation"}
        )

        get = await async_client.get(f"/api/correction-log/{clean_log_language}")
        entry = next(e for e in get.json()["entries"] if e["id"] == log_id)

        assert entry["original_text"] == BIBLE_ENTRY["original_text"]
        assert entry["correction"] == BIBLE_ENTRY["correction"]
        assert entry["content_type"] == BIBLE_ENTRY["content_type"]
        assert entry["content_reference"] == BIBLE_ENTRY["content_reference"]

    @pytest.mark.asyncio
    async def test_put_extra_body_fields_ignored(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """Extra fields in PUT body (e.g., correction) are ignored — only what_was_wrong changes."""
        log_id = await _append(async_client, clean_log_language, BIBLE_ENTRY)

        resp = await async_client.put(
            f"/api/correction-log/{clean_log_language}/{log_id}",
            json={
                "what_was_wrong": "Legit update",
                "correction": "Should be ignored",
                "original_text": "Should be ignored too",
            }
        )
        assert resp.status_code == 200

        get = await async_client.get(f"/api/correction-log/{clean_log_language}")
        entry = next(e for e in get.json()["entries"] if e["id"] == log_id)

        assert entry["what_was_wrong"] == "Legit update"
        assert entry["correction"] == BIBLE_ENTRY["correction"]
        assert entry["original_text"] == BIBLE_ENTRY["original_text"]

    @pytest.mark.asyncio
    async def test_put_unknown_log_id_returns_404(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """PUT with a valid-format but nonexistent ObjectId → 404."""
        from bson import ObjectId
        fake_id = str(ObjectId())  # valid format, nonexistent
        resp = await async_client.put(
            f"/api/correction-log/{clean_log_language}/{fake_id}",
            json={"what_was_wrong": "Should not work"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_put_invalid_objectid_returns_404(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """PUT with a malformed ObjectId string → 404 (not 500)."""
        resp = await async_client.put(
            f"/api/correction-log/{clean_log_language}/not-a-valid-objectid",
            json={"what_was_wrong": "Should not work"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_put_allows_empty_what_was_wrong(
        self, async_client: AsyncClient, clean_log_language: str
    ):
        """PUT allows clearing the explanation (empty string is valid for updates)."""
        log_id = await _append(async_client, clean_log_language, BIBLE_ENTRY)

        resp = await async_client.put(
            f"/api/correction-log/{clean_log_language}/{log_id}",
            json={"what_was_wrong": ""}
        )
        assert resp.status_code == 200

        get = await async_client.get(f"/api/correction-log/{clean_log_language}")
        entry = next(e for e in get.json()["entries"] if e["id"] == log_id)
        assert entry["what_was_wrong"] == ""
