"""
Tests for back_end/migrations/reconcile_bible_books_shape.py.

Covers:
- Pass 1 (resync from bible_texts): --apply overwrites legacy-shape docs to
  canonical `[{chapter, verse_count}]`; idempotent on a second --apply.
- Dry-run touches no docs on either pass.
- Pass 2 (orphan rebuild): rebuilds legacy-shape docs with no matching
  bible_texts rows from get_chapters_for_book; SKIPS (and warns on) orphan
  docs whose book_name isn't in BIBLE_CHAPTER_VERSES, never zeroing them out.
"""

import uuid
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from constants import Collection
from migrations.reconcile_bible_books_shape import run


@pytest_asyncio.fixture
async def clean_recon_language(connected_db) -> AsyncGenerator[str, None]:
    """Provide a unique language_code and clean its docs before and after."""
    db = connected_db.get_database()
    await db[Collection.BIBLE_TEXTS].delete_many(
        {"language_code": {"$regex": "^test_recon_"}}
    )
    await db[Collection.BIBLE_BOOKS].delete_many(
        {"language_code": {"$regex": "^test_recon_"}}
    )
    lang = f"test_recon_{uuid.uuid4().hex[:8]}"
    yield lang
    await db[Collection.BIBLE_TEXTS].delete_many({"language_code": lang})
    await db[Collection.BIBLE_BOOKS].delete_many({"language_code": lang})


async def _seed_bible_texts(
    connected_db, lang: str, book_code: str, chapters_verse_counts: list[tuple[int, int]]
) -> None:
    db = connected_db.get_database()
    docs = [
        {
            "language_code": lang,
            "book_code": book_code,
            "chapter": chapter,
            "verse": verse,
            "english_text": "test text",
            "created_at": datetime(2024, 1, 1),
        }
        for chapter, verse_count in chapters_verse_counts
        for verse in range(1, verse_count + 1)
    ]
    if docs:
        await db[Collection.BIBLE_TEXTS].insert_many(docs)


def _legacy_chapters(chapters_verse_counts: list[tuple[int, int]]) -> list[dict]:
    return [
        {
            "chapter_number": chapter,
            "verse_count": verse_count,
            "verses": [
                {"verse_number": v, "english_text": "", "translated_text": "", "comments": ""}
                for v in range(1, verse_count + 1)
            ],
        }
        for chapter, verse_count in chapters_verse_counts
    ]


async def _seed_legacy_bible_books_doc(
    connected_db,
    lang: str,
    book_code: str,
    book_name: str,
    chapters_verse_counts: list[tuple[int, int]],
) -> None:
    db = connected_db.get_database()
    chapters = _legacy_chapters(chapters_verse_counts)
    doc = {
        "language_code": lang,
        "language_name": lang,
        "book_name": book_name,
        "book_code": book_code,
        "total_chapters": len(chapters),
        "total_verses": sum(vc for _, vc in chapters_verse_counts),
        "chapters": chapters,
        "created_at": datetime(2024, 1, 1),
        "translation_status": "not_started",
        "metadata": {"testament": "old", "canonical_order": 1},
    }
    await db[Collection.BIBLE_BOOKS].insert_one(doc)


async def _get_bible_books_doc(connected_db, lang: str, book_code: str) -> dict:
    db = connected_db.get_database()
    doc = await db[Collection.BIBLE_BOOKS].find_one(
        {"language_code": lang, "book_code": book_code}
    )
    assert doc is not None, f"No bible_books doc for {lang}/{book_code}"
    return doc


class TestPass1ResyncFromTexts:
    @pytest.mark.asyncio
    async def test_apply_overwrites_legacy_shape_to_canonical(
        self, connected_db, clean_recon_language
    ):
        lang = clean_recon_language
        await _seed_bible_texts(connected_db, lang, "ruth", [(1, 22), (2, 23)])
        await _seed_legacy_bible_books_doc(
            connected_db, lang, "ruth", "Ruth", [(1, 22), (2, 23)]
        )

        await run(apply=True)

        doc = await _get_bible_books_doc(connected_db, lang, "ruth")
        assert doc["chapters"] == [
            {"chapter": 1, "verse_count": 22},
            {"chapter": 2, "verse_count": 23},
        ]
        assert doc["total_chapters"] == 2
        assert doc["total_verses"] == 45
        for ch in doc["chapters"]:
            assert "chapter_number" not in ch
            assert "verses" not in ch

    @pytest.mark.asyncio
    async def test_idempotent_second_apply(self, connected_db, clean_recon_language):
        lang = clean_recon_language
        await _seed_bible_texts(connected_db, lang, "ruth", [(1, 22)])
        await _seed_legacy_bible_books_doc(connected_db, lang, "ruth", "Ruth", [(1, 22)])

        await run(apply=True)
        doc_first = await _get_bible_books_doc(connected_db, lang, "ruth")

        await run(apply=True)
        doc_second = await _get_bible_books_doc(connected_db, lang, "ruth")

        assert doc_first["chapters"] == doc_second["chapters"]
        assert doc_first["total_chapters"] == doc_second["total_chapters"]
        assert doc_first["total_verses"] == doc_second["total_verses"]

    @pytest.mark.asyncio
    async def test_dry_run_touches_no_docs(self, connected_db, clean_recon_language):
        lang = clean_recon_language
        await _seed_bible_texts(connected_db, lang, "ruth", [(1, 22)])
        await _seed_legacy_bible_books_doc(connected_db, lang, "ruth", "Ruth", [(1, 22)])

        written = await run(apply=False)

        assert written == 0
        doc = await _get_bible_books_doc(connected_db, lang, "ruth")
        # Still legacy shape — untouched.
        assert doc["chapters"][0].get("chapter_number") == 1
        assert "verses" in doc["chapters"][0]


class TestPass2OrphanRebuild:
    @pytest.mark.asyncio
    async def test_rebuilds_orphan_with_canonical_book_name(
        self, connected_db, clean_recon_language
    ):
        """No bible_texts rows for this language — pass 2 rebuilds from get_chapters_for_book."""
        lang = clean_recon_language
        # Deliberately WRONG legacy verse counts, to prove the rebuild uses the
        # canonical BIBLE_CHAPTER_VERSES source, not the stale embedded data.
        await _seed_legacy_bible_books_doc(connected_db, lang, "ruth", "Ruth", [(1, 1), (2, 1)])

        await run(apply=True)

        doc = await _get_bible_books_doc(connected_db, lang, "ruth")
        assert doc["chapters"] == [
            {"chapter": 1, "verse_count": 22},
            {"chapter": 2, "verse_count": 23},
            {"chapter": 3, "verse_count": 18},
            {"chapter": 4, "verse_count": 22},
        ]
        assert doc["total_chapters"] == 4
        assert doc["total_verses"] == 85

    @pytest.mark.asyncio
    async def test_dry_run_does_not_touch_orphan(self, connected_db, clean_recon_language):
        lang = clean_recon_language
        await _seed_legacy_bible_books_doc(connected_db, lang, "ruth", "Ruth", [(1, 1)])

        written = await run(apply=False)

        assert written == 0
        doc = await _get_bible_books_doc(connected_db, lang, "ruth")
        assert doc["chapters"][0].get("chapter_number") == 1

    @pytest.mark.asyncio
    async def test_skips_orphan_with_non_canonical_book_name(
        self, connected_db, clean_recon_language, caplog
    ):
        """book_name not in BIBLE_CHAPTER_VERSES must be skipped, not zeroed out."""
        lang = clean_recon_language
        bogus_book_name = f"not_a_real_book_{uuid.uuid4().hex[:6]}"
        await _seed_legacy_bible_books_doc(
            connected_db, lang, "xyz", bogus_book_name, [(1, 5)]
        )

        with caplog.at_level("WARNING"):
            await run(apply=True)

        doc = await _get_bible_books_doc(connected_db, lang, "xyz")
        # Untouched — still legacy shape, not zeroed out.
        assert doc["chapters"] == _legacy_chapters([(1, 5)])
        assert doc["total_chapters"] == 1
        assert doc["total_verses"] == 5
        assert any(
            "non-canonical" in rec.message and bogus_book_name in rec.message
            for rec in caplog.records
        )
