"""
Tests for back_end/migrations/add_note_titles.py.

Covers:
- _derive_title pure logic (empty/short/long/newlines/whitespace)
- run(apply=True) integration: backfills only missing titles, idempotent,
  preserves updated_at on touched documents.
- Self-verify negative path: if a doc is mutated mid-run, exit(1).
"""

import pytest
import pytest_asyncio
from datetime import datetime
from typing import AsyncGenerator
import uuid

from constants import Collection
from migrations.add_note_titles import (
    _derive_title,
    _note_needs_backfill,
    run,
    _verify_all_notes_have_title,
)


# === Unit tests for the pure helper ===

class TestDeriveTitle:
    def test_empty_string(self):
        assert _derive_title("") == "Untitled"

    def test_none_safe(self):
        # function signature is str, but defensive against legacy None values
        assert _derive_title(None) == "Untitled"  # type: ignore[arg-type]

    def test_whitespace_only(self):
        assert _derive_title("   \n  \t") == "Untitled"

    def test_short_text_returned_verbatim(self):
        text = "kupiga uses -li- past tense"
        assert _derive_title(text) == text

    def test_exactly_60_chars_returned_verbatim(self):
        text = "x" * 60
        assert _derive_title(text) == text
        assert "…" not in _derive_title(text)

    def test_long_text_word_boundary_trim(self):
        text = "The verb 'kupiga' has at least twelve idiomatic uses including 'to dial a number'"
        result = _derive_title(text)
        assert result.endswith("…")
        assert len(result) <= 61  # 60 cut + ellipsis
        assert "\n" not in result

    def test_long_text_no_internal_space_falls_through(self):
        # If the first 60 chars are a single token, rfind returns -1 → fallback
        # to raw cut; behaviour is documented: cut + "…"
        text = "x" * 80
        result = _derive_title(text)
        assert result.endswith("…")
        assert len(result) <= 61

    def test_newlines_collapsed_to_single_space(self):
        text = "Line one\nLine two\nLine three"
        result = _derive_title(text)
        assert "\n" not in result
        assert result == "Line one Line two Line three"

    def test_runs_of_whitespace_collapsed(self):
        text = "Word1     Word2\t\tWord3"
        result = _derive_title(text)
        assert result == "Word1 Word2 Word3"


# === note_needs_backfill ===

class TestNoteNeedsBackfill:
    def test_missing_title(self):
        assert _note_needs_backfill({"text": "x"}) is True

    def test_none_title(self):
        assert _note_needs_backfill({"title": None, "text": "x"}) is True

    def test_empty_string_title(self):
        assert _note_needs_backfill({"title": "", "text": "x"}) is True

    def test_whitespace_only_title(self):
        assert _note_needs_backfill({"title": "   ", "text": "x"}) is True

    def test_non_string_title(self):
        assert _note_needs_backfill({"title": 123, "text": "x"}) is True

    def test_real_title(self):
        assert _note_needs_backfill({"title": "Real", "text": "x"}) is False


# === Integration tests against MongoDB ===

@pytest_asyncio.fixture
async def clean_migration_language(connected_db) -> AsyncGenerator[str, None]:
    """Provide a unique language_code and clean its language_notes doc afterward.

    Also sweeps stale test_mig_* docs from prior runs so global-scan assertions
    (the migration counts backfills across every doc) stay deterministic.
    """
    db = connected_db.get_database()
    # Sweep leftovers from earlier interrupted runs of these tests.
    await db[Collection.LANGUAGE_NOTES].delete_many(
        {"language_code": {"$regex": "^test_mig_"}}
    )
    lang = f"test_mig_{uuid.uuid4().hex[:8]}"
    yield lang
    await db[Collection.LANGUAGE_NOTES].delete_many({"language_code": lang})


async def _seed_doc(
    connected_db, language_code: str, notes: list[dict], updated_at: datetime
) -> None:
    db = connected_db.get_database()
    await db[Collection.LANGUAGE_NOTES].insert_one({
        "language_code": language_code,
        "notes": notes,
        "updated_at": updated_at,
    })


async def _get_doc(connected_db, language_code: str) -> dict:
    db = connected_db.get_database()
    doc = await db[Collection.LANGUAGE_NOTES].find_one({"language_code": language_code})
    assert doc is not None, f"No doc found for {language_code}"
    return doc


class TestRunIntegration:
    """End-to-end: run() against a real MongoDB doc.

    Note: run() scans the entire collection and returns a global backfill count.
    These tests therefore assert on the SPECIFIC doc they seeded — not the
    global return value — to stay robust against other docs that may live in
    the shared dev database.
    """

    @pytest.mark.asyncio
    async def test_backfills_missing_title_only(
        self, connected_db, clean_migration_language: str
    ):
        """Only notes without a non-empty title are touched; rest untouched."""
        lang = clean_migration_language
        doc_updated = datetime(2024, 6, 1)
        await _seed_doc(connected_db, lang, [
            {
                "id": "legacy-1",
                # no title → should be backfilled
                "text": "kupiga uses -li- past tense",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
            {
                "id": "preset-2",
                "title": "Existing title",
                "text": "body",
                "created_at": datetime(2024, 1, 2),
                "updated_at": datetime(2024, 1, 2),
            },
        ], updated_at=doc_updated)

        await run(apply=True)

        doc = await _get_doc(connected_db, lang)
        notes_by_id = {n["id"]: n for n in doc["notes"]}
        assert notes_by_id["legacy-1"]["title"] == "kupiga uses -li- past tense"
        assert notes_by_id["preset-2"]["title"] == "Existing title"

    @pytest.mark.asyncio
    async def test_does_not_touch_document_updated_at(
        self, connected_db, clean_migration_language: str
    ):
        """Migration must NOT change the document's updated_at (P9)."""
        lang = clean_migration_language
        original_updated = datetime(2024, 6, 1, 12, 0, 0)
        await _seed_doc(connected_db, lang, [
            {
                "id": "legacy-1",
                "text": "Some legacy body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=original_updated)

        await run(apply=True)

        doc = await _get_doc(connected_db, lang)
        assert doc["updated_at"] == original_updated

    @pytest.mark.asyncio
    async def test_does_not_touch_note_updated_at(
        self, connected_db, clean_migration_language: str
    ):
        """Migration must NOT change a note's updated_at (P9)."""
        lang = clean_migration_language
        note_updated = datetime(2024, 1, 1, 8, 30, 0)
        await _seed_doc(connected_db, lang, [
            {
                "id": "legacy-1",
                "text": "Body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": note_updated,
            },
        ], updated_at=datetime(2024, 6, 1))

        await run(apply=True)

        doc = await _get_doc(connected_db, lang)
        assert doc["notes"][0]["updated_at"] == note_updated

    @pytest.mark.asyncio
    async def test_whitespace_text_yields_untitled(
        self, connected_db, clean_migration_language: str
    ):
        """A legacy note whose text is whitespace-only becomes 'Untitled'."""
        lang = clean_migration_language
        await _seed_doc(connected_db, lang, [
            {
                "id": "n",
                "text": "   \n  ",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=datetime(2024, 1, 1))

        await run(apply=True)
        doc = await _get_doc(connected_db, lang)
        assert doc["notes"][0]["title"] == "Untitled"

    @pytest.mark.asyncio
    async def test_idempotent_second_run_is_noop(
        self, connected_db, clean_migration_language: str
    ):
        """After --apply, our seeded doc is stable: a second --apply does not change it."""
        lang = clean_migration_language
        await _seed_doc(connected_db, lang, [
            {
                "id": "n",
                "text": "Original body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=datetime(2024, 1, 1))

        await run(apply=True)
        doc_after_first = await _get_doc(connected_db, lang)
        title_after_first = doc_after_first["notes"][0]["title"]

        await run(apply=True)
        doc_after_second = await _get_doc(connected_db, lang)
        assert doc_after_second["notes"][0]["title"] == title_after_first

    @pytest.mark.asyncio
    async def test_dry_run_does_not_write(
        self, connected_db, clean_migration_language: str
    ):
        """Without --apply, no write occurs and the stored note still lacks title."""
        lang = clean_migration_language
        await _seed_doc(connected_db, lang, [
            {
                "id": "n",
                "text": "Body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=datetime(2024, 1, 1))

        await run(apply=False)

        doc = await _get_doc(connected_db, lang)
        assert "title" not in doc["notes"][0] or not (doc["notes"][0].get("title") or "").strip()


class TestVerifyHelper:
    """_verify_all_notes_have_title walks every doc and surfaces title-less notes."""

    @pytest.mark.asyncio
    async def test_returns_empty_on_clean_db(
        self, connected_db, clean_migration_language: str
    ):
        lang = clean_migration_language
        await _seed_doc(connected_db, lang, [
            {
                "id": "n",
                "title": "ok",
                "text": "body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=datetime(2024, 1, 1))

        collection = connected_db.get_database()[Collection.LANGUAGE_NOTES]
        # Pre-clean any other leftover docs that might still violate (defensive
        # against parallel/leaked fixtures): only assert our doc is healthy.
        bad = await _verify_all_notes_have_title(collection)
        assert not any(language == lang for language, _ in bad)

    @pytest.mark.asyncio
    async def test_flags_missing_title(
        self, connected_db, clean_migration_language: str
    ):
        lang = clean_migration_language
        await _seed_doc(connected_db, lang, [
            {
                "id": "broken",
                # no title field
                "text": "body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=datetime(2024, 1, 1))

        collection = connected_db.get_database()[Collection.LANGUAGE_NOTES]
        bad = await _verify_all_notes_have_title(collection)
        assert (lang, "broken") in bad


class TestSelfVerifyFails:
    """If run() writes but a doc still lacks a title afterward, raise SystemExit(1)."""

    @pytest.mark.asyncio
    async def test_self_verify_negative(
        self, connected_db, clean_migration_language: str, monkeypatch
    ):
        """
        Force the verify-pass to report a slipped note even after writes complete.
        Motor returns fresh collection objects on each db[name] access, so patching
        update_one in-place is unreliable; instead we simulate the verify-pass
        result, which is what `run()` actually gates on for the failure branch.
        """
        lang = clean_migration_language
        await _seed_doc(connected_db, lang, [
            {
                "id": "legacy",
                "text": "Body",
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
        ], updated_at=datetime(2024, 1, 1))

        from migrations import add_note_titles as mig

        async def _fake_verify(_collection):
            return [(lang, "legacy")]

        monkeypatch.setattr(mig, "_verify_all_notes_have_title", _fake_verify)

        with pytest.raises(SystemExit) as excinfo:
            await mig.run(apply=True)
        assert excinfo.value.code == 1
