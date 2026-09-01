"""
One-shot migration: reconcile `bible_books.chapters` to the canonical shape
`[{chapter: int, verse_count: int}]` (no embedded verses, no `chapter_number`
key), and backfill `total_chapters`/`total_verses` to match.

Two passes, both gated by --apply (dry-run touches nothing):

1. Resync every language that has `bible_texts` rows, via the existing
   `sync_bible_books_from_texts` aggregation (already produces the canonical
   shape). No aggregation logic is duplicated here — any future fix to that
   aggregation applies to this migration automatically.

2. Rebuild orphaned `bible_books` docs — legacy-shape docs whose language has
   NO matching `bible_texts` rows (so pass 1 can't reach them), from
   `get_chapters_for_book(book_name)`, the same canonical source
   `new_language.py` uses. If a doc's `book_name` isn't in
   `BIBLE_CHAPTER_VERSES` (e.g. stored via a lowercase-code fallback), the
   doc is SKIPPED and a warning is logged — it is never overwritten with
   `chapters: [], total_chapters: 0, total_verses: 0`, which would just
   trade one shape bug for a data-loss bug.

Idempotent — safe to re-run.

Run with no import in flight — the migration does full-array $set on
bible_books; concurrent import_bible/new_language/load_base_language calls
can race.

Run:
    cd back_end
    source nlm_backend_venv/bin/activate
    python -m migrations.reconcile_bible_books_shape            # dry-run
    python -m migrations.reconcile_bible_books_shape --apply    # write
"""

import argparse
import asyncio
import logging

from constants import Collection
from db_connector.connection import get_mongodb_connector
from utils.bible_generator.chapter_verse_numbers import get_chapters_for_book
from utils.usfm_parser.usfm_importer import sync_bible_books_from_texts

logger = logging.getLogger(__name__)


async def run(apply: bool) -> int:
    """Returns number of bible_books docs written (0 in dry-run mode)."""
    connector = await get_mongodb_connector()
    db = connector.get_database()
    bible_texts = db[Collection.BIBLE_TEXTS]
    bible_books = db[Collection.BIBLE_BOOKS]

    docs_written = 0

    # Pass 1: resync every language with bible_texts rows via the canonical
    # aggregation in sync_bible_books_from_texts.
    language_codes = await bible_texts.distinct("language_code")
    for lc in language_codes:
        if apply:
            docs_written += await sync_bible_books_from_texts(lc, connector)
        else:
            logger.info(f"[dry-run] would sync language_code={lc}")

    # Pass 2: rebuild orphaned bible_books docs (no matching bible_texts rows)
    # still sitting in the legacy {chapter_number, verses} shape.
    texts_language_codes = list(language_codes)
    orphan_cursor = bible_books.find({
        "language_code": {"$nin": texts_language_codes},
        "chapters.0.chapter_number": {"$exists": True},
    })

    async for doc in orphan_cursor:
        lc = doc.get("language_code", "?")
        book_code = doc.get("book_code", "?")
        book_name = doc.get("book_name", "")

        canonical = get_chapters_for_book(book_name)
        if not canonical:
            logger.warning(
                "Skipping orphan bible_books doc with non-canonical book_name: "
                f"language_code={lc}, book_code={book_code}, book_name={book_name!r}"
            )
            continue

        if apply:
            chapters = [{"chapter": ch, "verse_count": vc} for ch, vc in canonical]
            await bible_books.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "chapters": chapters,
                    "total_chapters": len(chapters),
                    "total_verses": sum(vc for _, vc in canonical),
                }},
            )
            docs_written += 1
        else:
            logger.info(f"[dry-run] would rebuild orphan {lc}/{book_code}")

    mode = "APPLIED" if apply else "DRY RUN"
    logger.info(
        "%s: %d languages scanned, %d bible_books docs written",
        mode, len(language_codes), docs_written,
    )

    return docs_written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write changes. Without this flag, runs in dry-run mode.")
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
