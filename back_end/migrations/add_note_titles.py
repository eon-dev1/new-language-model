"""
One-shot migration: add `title` field to every note in `language_notes`.

Idempotent — safe to re-run. Touches only notes where `title` is missing,
`None`, or empty after `.strip()`. Derives the title from the note's `text`
field using the same rule as the UI's natural truncation.

After --apply, runs a self-verification pass: re-scans every doc and confirms
every note has a non-empty `title`. Exits non-zero if any slipped through.
This is the real safety net — the schema_enforcer's embedded_schema recursion
only samples `sample_size` docs at startup, so it can miss embedded fields
in unsampled documents.

Run with no traffic in flight — the migration does full-array $set on each
language_notes document and is concurrency-unsafe vs. concurrent POST/DELETE.

Run:
    cd back_end
    source nlm_backend_venv/bin/activate
    python -m migrations.add_note_titles            # dry-run
    python -m migrations.add_note_titles --apply    # write + self-verify
"""

import argparse
import asyncio
import logging

from constants import Collection
from db_connector.connection import get_mongodb_connector

logger = logging.getLogger(__name__)

TITLE_MAX_DERIVED = 60


def _derive_title(text: str) -> str:
    """Produce a display title from body text. Used only by this migration."""
    flat = " ".join((text or "").split())
    if not flat:
        return "Untitled"
    if len(flat) <= TITLE_MAX_DERIVED:
        return flat
    cut = flat[:TITLE_MAX_DERIVED]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


def _note_needs_backfill(note: dict) -> bool:
    title = note.get("title")
    return not isinstance(title, str) or not title.strip()


async def run(apply: bool) -> int:
    """Returns number of notes backfilled. Raises SystemExit(1) if self-verify fails after --apply."""
    connector = await get_mongodb_connector()
    collection = connector.get_database()[Collection.LANGUAGE_NOTES]

    total_docs = 0
    docs_modified = 0
    notes_backfilled = 0

    async for doc in collection.find({}):
        total_docs += 1
        notes = doc.get("notes", []) or []
        changed = False
        for note in notes:
            if _note_needs_backfill(note):
                note["title"] = _derive_title(note.get("text", ""))
                notes_backfilled += 1
                changed = True
        if changed:
            docs_modified += 1
            if apply:
                await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"notes": notes}},  # updated_at intentionally NOT touched
                )

    mode = "APPLIED" if apply else "DRY RUN"
    logger.info(
        "%s: scanned %d docs, %d %s modified, %d notes backfilled",
        mode, total_docs, docs_modified,
        "were" if apply else "would be", notes_backfilled,
    )

    if apply:
        bad = await _verify_all_notes_have_title(collection)
        if bad:
            logger.error(
                "SELF-VERIFY FAILED: %d notes still lack a non-empty title after migration: %s",
                len(bad), bad[:10],
            )
            raise SystemExit(1)
        logger.info("SELF-VERIFY OK: every note has a non-empty title")

    return notes_backfilled


async def _verify_all_notes_have_title(collection) -> list[tuple[str, str]]:
    """Re-scan and return [(language_code, note_id), ...] for any note still missing title."""
    bad: list[tuple[str, str]] = []
    async for doc in collection.find({}):
        for note in doc.get("notes", []) or []:
            title = note.get("title")
            if not isinstance(title, str) or not title.strip():
                bad.append((doc.get("language_code", "?"), note.get("id", "?")))
    return bad


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write changes and self-verify. Without this flag, runs in dry-run mode.")
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
